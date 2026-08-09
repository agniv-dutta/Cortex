"""Think9 specialized model registry, dataset export, and evaluation helpers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median

from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.envelope import WorkflowContext, WorkflowInput
from app.core.ulid import new_id
from app.db.models import Chunk, Decision, DecisionBrief, Flag, Outcome
from app.db.models.feedback import FineTuneRun, Think9Model
from app.prompts import THINK9_BRIEF_SYSTEM
from app.providers.embedder import get_embedder
from app.providers.llm import LLMProvider, build_llm
from app.schemas.context import GeneralChunk, HistoricalDecision, PlaybookSection, QueryContext, RetrievedContext, RetrievalSummary
from app.schemas.feedback import FinetuneDatasetResponse, FinetuneExample, Think9EvalResult, Think9ModelRegisterRequest, Think9ModelResponse, Think9ModelStatusResponse
from app.services.synthesizer import DecisionSynthesizer


ROLE = "decision_brief"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _result_weight(result: str) -> float:
    return {"success": 1.0, "partial": 0.5, "failure": 0.0, "superseded": 0.0}.get(result, 0.0)


def _output_quality(result: str) -> str:
    if result == "success":
        return "success"
    if result == "partial":
        return "partial"
    if result == "failure":
        return "failure"
    return "superseded"


def _complexity_score(decision: Decision, brief: DecisionBrief, flags: list[Flag]) -> int:
    precedents = len((brief.brief or {}).get("precedents") or [])
    revision_round = brief.revision_round or 0
    flags_weight = len(flags)
    base = 1 + min(2, precedents // 2) + min(1, revision_round) + min(1, flags_weight // 2)
    if decision.decision_class in {"contract", "compliance"}:
        base += 1
    if decision.category in {"procurement", "brand"}:
        base += 1
    return max(1, min(5, base))


def _lessons_learned(brief: DecisionBrief, outcome: Outcome, flags: list[Flag]) -> list[str]:
    lessons: list[str] = []
    action = ((brief.brief or {}).get("recommended_action") or {}).get("action", "")
    rationale = ((brief.brief or {}).get("recommended_action") or {}).get("rationale", "")
    if action:
        lessons.append(f"Recommendation used: {action}")
    if rationale:
        lessons.append(f"Rationale pattern: {rationale[:180]}")
    if flags:
        lessons.append(f"Key conflict themes: {', '.join(sorted({f.flag_type for f in flags}))}")
    if outcome.narrative:
        lessons.append(f"Outcome note: {outcome.narrative[:180]}")
    if outcome.result == "failure":
        lessons.append("Lesson: lower confidence when evidence is thin or contradictory.")
    if outcome.result == "success":
        lessons.append("Lesson: preserve this precedent shape for future matching.")
    return lessons[:5]


def _decision_instruction(decision: Decision) -> str:
    return f"Produce a Think9 decision brief for: {decision.statement}"


def _build_messages(decision: Decision, brief: DecisionBrief) -> list[dict]:
    brief_data = brief.brief or {}
    user = {
        "statement": decision.statement,
        "category": decision.category,
        "decision_class": decision.decision_class,
        "brands": decision.brands or [],
        "context_notes": decision.context_notes or "",
        "requester": decision.requester or "",
        "think9_style": "Use Think9 executive brief format with grounded precedents and explicit gates.",
    }
    assistant = {
        "recommended_action": brief_data.get("recommended_action", {}),
        "precedents": brief_data.get("precedents", []),
        "risk_factors": brief_data.get("risk_factors", {}),
        "approval_flow": brief_data.get("approval_flow", {}),
        "evidence_gaps": brief_data.get("evidence_gaps", []),
        "provenance_chunks": brief_data.get("provenance_chunks", []),
    }
    return [
        {"role": "system", "content": THINK9_BRIEF_SYSTEM},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        {"role": "assistant", "content": json.dumps(assistant, ensure_ascii=False)},
    ]


def _decision_rows(session: Session) -> list[tuple[Decision, DecisionBrief, Outcome, list[Flag]]]:
    brief_by_decision: dict[str, DecisionBrief] = {}
    for brief in session.query(DecisionBrief).order_by(desc(DecisionBrief.created_at)).all():
        if brief.decision_id and brief.decision_id not in brief_by_decision:
            brief_by_decision[brief.decision_id] = brief

    flags_by_brief: dict[str, list[Flag]] = {}
    for flag in session.query(Flag).all():
        flags_by_brief.setdefault(flag.brief_id, []).append(flag)

    rows: list[tuple[Decision, DecisionBrief, Outcome, list[Flag]]] = []
    for outcome in session.query(Outcome).all():
        if outcome.result == "superseded":
            continue
        decision = session.get(Decision, outcome.decision_id)
        brief = brief_by_decision.get(outcome.decision_id)
        if decision is None or brief is None:
            continue
        rows.append((decision, brief, outcome, flags_by_brief.get(brief.id, [])))
    rows.sort(key=lambda item: item[0].created_at)
    return rows


def build_dataset(session: Session, *, holdout_fraction: float | None = None, min_samples: int | None = None) -> tuple[list[dict], dict]:
    settings = get_settings()
    holdout_fraction = holdout_fraction if holdout_fraction is not None else settings.finetune_holdout_fraction
    min_samples = min_samples if min_samples is not None else settings.finetune_min_samples

    rows_src = _decision_rows(session)
    total = len(rows_src)
    split_index = max(1, int(math.floor(total * (1.0 - holdout_fraction))))
    training_rows = 0
    holdout_rows = 0
    rows: list[dict] = []
    for idx, (decision, brief, outcome, flags) in enumerate(rows_src):
        split = "train" if idx < split_index else "holdout"
        if split == "train":
            training_rows += 1
        else:
            holdout_rows += 1
        brief_payload = brief.brief or {}
        record = {
            "instruction": _decision_instruction(decision),
            "input": {
                "statement": decision.statement,
                "category": decision.category,
                "decision_class": decision.decision_class,
                "brands": decision.brands or [],
                "context_notes": decision.context_notes or "",
                "requester": decision.requester or "",
            },
            "output": brief_payload,
            "messages": _build_messages(decision, brief),
            "meta": {
                "decision_id": decision.id,
                "brief_id": brief.id,
                "category": decision.category,
                "decision_class": decision.decision_class,
                "brands": decision.brands or [],
                "complexity": _complexity_score(decision, brief, flags),
                "outcome_quality": _output_quality(outcome.result),
                "outcome": outcome.result,
                "confidence": brief.confidence,
                "lessons_learned": _lessons_learned(brief, outcome, flags),
                "precedent_count": len(brief_payload.get("precedents") or []),
                "flag_types": sorted({flag.flag_type for flag in flags}),
                "split": split,
                "created_at": decision.created_at.isoformat(),
            },
        }
        rows.append(record)

    manifest = {
        "dataset_version": datetime.now(timezone.utc).strftime("think9-%Y%m%d-%H%M%S"),
        "role": ROLE,
        "rows": total,
        "training_rows": training_rows,
        "holdout_rows": holdout_rows,
        "meets_min_samples": total >= min_samples,
        "holdout_fraction": holdout_fraction,
        "min_samples": min_samples,
        "schema": "messages+meta+brief-output",
        "specialization": "Think9 decision brief generation",
    }
    return rows, manifest


def export_filename(dataset_version: str | None = None) -> str:
    dataset_version = dataset_version or datetime.now(timezone.utc).strftime("think9-%Y%m%d")
    return f"think9_finetune_{dataset_version}.jsonl"


def _chunk_context(session: Session, chunk_ids: list[str]) -> RetrievedContext:
    chunks = (
        session.query(Chunk)
        .options(selectinload(Chunk.document))
        .filter(Chunk.id.in_(chunk_ids))
        .all()
    )
    general: list[GeneralChunk] = []
    decisions: list[HistoricalDecision] = []
    playbooks: list[PlaybookSection] = []
    for chunk in chunks:
        doc = chunk.document
        citation = f"[{doc.id}, {chunk.id}, {doc.doc_type}]"
        if doc.doc_type == "decision":
            decisions.append(
                HistoricalDecision(
                    decision_id=doc.id,
                    title=doc.title,
                    category=doc.category or "",
                    outcome=None,
                    date=str(doc.created_at.date()) if doc.created_at else None,
                    relevance=1.0,
                    hybrid_score=1.0,
                    match_reason=chunk.content[:220],
                    chunk_refs=[chunk.id],
                )
            )
        elif doc.doc_type == "playbook":
            playbooks.append(
                PlaybookSection(
                    document_id=doc.id,
                    section=doc.title,
                    chunk_id=chunk.id,
                    relevance=1.0,
                    applies_because=chunk.content[:220],
                )
            )
        else:
            general.append(
                GeneralChunk(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    title=doc.title,
                    content=chunk.content,
                    doc_type=doc.doc_type,
                    relevance=1.0,
                    citation=citation,
                )
            )
    return RetrievedContext(
        retrieval_summary=RetrievalSummary(
            candidates_considered=len(chunks),
            reranked_top=len(chunks),
            evidence_coverage={},
            min_relevance=1.0 if chunks else 0.0,
            mode="hybrid" if chunks else "empty",
            note=None,
        ),
        historical_decisions=decisions,
        playbook_sections=playbooks,
        general_context=general,
    )


def _query_context_from_decision(decision: Decision) -> QueryContext:
    return QueryContext(
        category=decision.category,
        sub_category=decision.decision_class,
        category_confidence=1.0,
        brands=decision.brands or ["all"],
        functions=[],
        urgency="medium",
        required_expertise=[],
        key_facts=[],
        intent="decision_brief",
    )


@dataclass
class _EvalRun:
    action_similarity: float
    confidence_error: float
    citation_overlap: float
    latency_ms: float
    approx_cost_usd: float


def _select_rows(rows: list[tuple[Decision, DecisionBrief, Outcome, list[Flag]]], holdout_fraction: float, sample_size: int) -> list[tuple[Decision, DecisionBrief, Outcome, list[Flag]]]:
    if not rows:
        return []
    split_index = max(1, int(math.floor(len(rows) * (1.0 - holdout_fraction))))
    heldout = rows[split_index:] if split_index < len(rows) else rows[-max(1, sample_size):]
    return heldout[:sample_size]


def _build_llm(provider: str | None, model: str | None, fallback_tier: str) -> LLMProvider:
    settings = get_settings()
    if provider and model:
        return build_llm(provider, model, settings)
    return build_llm(
        settings.think9_brief_provider if fallback_tier == "brief" else settings.premium_provider,
        settings.think9_brief_model or settings.premium_model if fallback_tier == "brief" else settings.premium_model,
        settings,
    )


def _generate_brief(session: Session, llm: LLMProvider, decision: Decision, brief: DecisionBrief, outcome: Outcome) -> tuple[dict, float]:
    chunk_ids = list((brief.brief or {}).get("provenance_chunks") or [])
    rc = _chunk_context(session, chunk_ids)
    qc = _query_context_from_decision(decision)
    envelope = WorkflowContext(
        trace_id=new_id("trc"),
        input=WorkflowInput(
            question=decision.statement,
            channel="api",
            user_id=decision.requester,
            session_id=None,
            context_notes=decision.context_notes,
        ),
        stage={"name": "orchestrator", "attempt": 1, "status": "ok"},
    )
    synth = DecisionSynthesizer(session, get_embedder(), llm_override=llm)
    generated, _ = synth.synthesize(envelope, qc, rc, None)
    return generated.model_dump(), len(json.dumps(generated.model_dump(), ensure_ascii=False))


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


class Think9ModelService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def export_dataset(self, *, holdout_fraction: float | None = None, min_samples: int | None = None) -> FinetuneDatasetResponse:
        rows, manifest = build_dataset(self.session, holdout_fraction=holdout_fraction, min_samples=min_samples)
        filename = export_filename(manifest["dataset_version"])
        export_dir = Path(__file__).resolve().parents[3] / "data" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        target = export_dir / filename
        target.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

        self.session.add(
            FineTuneRun(
                id=new_id("ftr"),
                role=ROLE,
                kind="export",
                status="completed",
                dataset_version=manifest["dataset_version"],
                samples=manifest["rows"],
                payload=manifest,
                metrics={"training_rows": manifest["training_rows"], "holdout_rows": manifest["holdout_rows"]},
            )
        )
        self.session.commit()
        preview = [FinetuneExample(**rows[i]) for i in range(min(5, len(rows)))]
        return FinetuneDatasetResponse(
            rows=len(rows),
            filename=filename,
            holdout_rows=manifest["holdout_rows"],
            training_rows=manifest["training_rows"],
            preview=preview,
            manifest=manifest,
        )

    def register_model(self, body: Think9ModelRegisterRequest) -> Think9ModelResponse:
        if body.activate:
            self.session.query(Think9Model).filter_by(role=body.role, active=True).update({"active": False})
        row = Think9Model(
            id=new_id("t9m"),
            role=body.role,
            provider=body.provider,
            model_name=body.model_name,
            base_model=body.base_model,
            dataset_version=body.dataset_version,
            active=body.activate,
            samples=0,
            train_metrics={},
            eval_metrics={},
            notes=body.notes,
        )
        self.session.add(row)
        self.session.add(
            FineTuneRun(
                id=new_id("ftr"),
                role=body.role,
                kind="deploy",
                status="completed",
                dataset_version=body.dataset_version,
                samples=0,
                payload=body.model_dump(),
                metrics={"active": body.activate},
            )
        )
        self.session.commit()
        return self._row_to_response(row)

    def status(self, role: str = ROLE) -> Think9ModelStatusResponse:
        rows = (
            self.session.query(Think9Model)
            .filter_by(role=role)
            .order_by(desc(Think9Model.created_at))
            .all()
        )
        history = [self._row_to_response(row) for row in rows]
        active = next((row for row in history if row.active), None)
        return Think9ModelStatusResponse(active=active, history=history)

    def evaluate(
        self,
        *,
        mode: str = "historical",
        sample_size: int = 25,
        holdout_fraction: float | None = None,
        candidate_provider: str | None = None,
        candidate_model: str | None = None,
        baseline_provider: str | None = None,
        baseline_model: str | None = None,
    ) -> Think9EvalResult:
        rows = _decision_rows(self.session)
        holdout_fraction = holdout_fraction if holdout_fraction is not None else get_settings().finetune_holdout_fraction
        sample = _select_rows(rows, holdout_fraction, sample_size)
        if not sample:
            return Think9EvalResult(samples=0)

        active = self.status().active
        if candidate_provider is None and candidate_model is None and active is not None:
            candidate_provider = active.provider
            candidate_model = active.model_name
        baseline_provider = baseline_provider or get_settings().premium_provider
        baseline_model = baseline_model or get_settings().premium_model
        candidate_llm = _build_llm(candidate_provider, candidate_model, "brief")
        baseline_llm = _build_llm(baseline_provider, baseline_model, "premium")

        candidate_runs: list[_EvalRun] = []
        baseline_runs: list[_EvalRun] = []

        for decision, brief, outcome, _flags in sample:
            gold_action = ((brief.brief or {}).get("recommended_action") or {}).get("action", "")
            gold_conf = float(brief.confidence or 0.0)

            start = datetime.now(timezone.utc)
            cand_brief, cand_prompt_size = _generate_brief(self.session, candidate_llm, decision, brief, outcome)
            cand_latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
            cand_action = ((cand_brief.get("recommended_action") or {}).get("action", ""))
            cand_conf = float((cand_brief.get("recommended_action") or {}).get("confidence", 0.0))
            cand_citations = len(cand_brief.get("provenance_chunks") or [])
            gold_citations = len((brief.brief or {}).get("provenance_chunks") or [])
            candidate_runs.append(
                _EvalRun(
                    action_similarity=_similarity(cand_action, gold_action),
                    confidence_error=abs(cand_conf - gold_conf),
                    citation_overlap=(cand_citations / gold_citations) if gold_citations else 0.0,
                    latency_ms=cand_latency,
                    approx_cost_usd=round((cand_prompt_size / 4.0) * 0.000003 + 0.01, 6),
                )
            )

            start = datetime.now(timezone.utc)
            base_brief, base_prompt_size = _generate_brief(self.session, baseline_llm, decision, brief, outcome)
            base_latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
            base_action = ((base_brief.get("recommended_action") or {}).get("action", ""))
            base_conf = float((base_brief.get("recommended_action") or {}).get("confidence", 0.0))
            base_citations = len(base_brief.get("provenance_chunks") or [])
            baseline_runs.append(
                _EvalRun(
                    action_similarity=_similarity(base_action, gold_action),
                    confidence_error=abs(base_conf - gold_conf),
                    citation_overlap=(base_citations / gold_citations) if gold_citations else 0.0,
                    latency_ms=base_latency,
                    approx_cost_usd=round((base_prompt_size / 4.0) * 0.000003 + 0.01, 6),
                )
            )

        def summarize(runs: list[_EvalRun]) -> dict:
            return {
                "recommendation_match": round(sum(r.action_similarity for r in runs) / len(runs), 3),
                "confidence_mae": round(sum(r.confidence_error for r in runs) / len(runs), 3),
                "citation_overlap": round(sum(r.citation_overlap for r in runs) / len(runs), 3),
                "latency_ms_p50": round(float(median([r.latency_ms for r in runs])), 2),
                "latency_ms_p95": round(sorted(r.latency_ms for r in runs)[max(0, math.ceil(len(runs) * 0.95) - 1)], 2),
                "cost_usd": round(sum(r.approx_cost_usd for r in runs), 4),
                "samples": len(runs),
            }

        candidate_summary = summarize(candidate_runs)
        baseline_summary = summarize(baseline_runs)
        comparison = {
            "match_delta": round(candidate_summary["recommendation_match"] - baseline_summary["recommendation_match"], 3),
            "confidence_mae_delta": round(baseline_summary["confidence_mae"] - candidate_summary["confidence_mae"], 3),
            "citation_overlap_delta": round(candidate_summary["citation_overlap"] - baseline_summary["citation_overlap"], 3),
            "latency_ms_delta": round(baseline_summary["latency_ms_p50"] - candidate_summary["latency_ms_p50"], 2),
            "cost_delta": round(candidate_summary["cost_usd"] - baseline_summary["cost_usd"], 4),
        }

        result = Think9EvalResult(
            candidate=candidate_summary,
            baseline=baseline_summary,
            comparison=comparison,
            samples=len(sample),
            latency_ms_p50=candidate_summary["latency_ms_p50"],
            latency_ms_p95=candidate_summary["latency_ms_p95"],
            cost_usd_candidate=candidate_summary["cost_usd"],
            cost_usd_baseline=baseline_summary["cost_usd"],
        )

        self.session.add(
            FineTuneRun(
                id=new_id("ftr"),
                role=ROLE,
                kind="eval",
                status="completed",
                dataset_version=None,
                samples=len(sample),
                payload={"mode": mode, "sample_size": sample_size, "holdout_fraction": holdout_fraction},
                metrics=result.model_dump(),
            )
        )
        self.session.commit()
        return result

    @staticmethod
    def _row_to_response(row: Think9Model) -> Think9ModelResponse:
        return Think9ModelResponse(
            id=row.id,
            role=row.role,
            provider=row.provider,
            model_name=row.model_name,
            base_model=row.base_model,
            dataset_version=row.dataset_version,
            active=row.active,
            samples=row.samples,
            train_metrics=row.train_metrics,
            eval_metrics=row.eval_metrics,
            notes=row.notes,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )

