"""Builds the decision transparency payload for UI consumption."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.db.models import BriefChunk, Chunk, DecisionBrief, Document, Flag, PrecedentStat
from app.schemas.brief import DraftBrief, Validation
from app.schemas.context import RetrievedContext
from app.schemas.transparency import (
    ConfidenceReasoningItem,
    DecisionTransparency,
    MissingDataItem,
    PlaybookCheckItem,
    RetrievedDocumentInsight,
)


def _percent(value: float | None) -> float:
    if value is None:
        return 0.0
    return round(value * 100.0, 0) if 0.0 <= value <= 1.0 else round(value, 0)


def _doc_source(doc_type: str) -> str:
    if doc_type == "decision":
        return "Historical decision"
    if doc_type in {"playbook", "guideline"}:
        return "Playbook"
    if doc_type == "learning":
        return "Learning"
    return doc_type.replace("_", " ").title() if doc_type else "Evidence"


def _top_provenance_candidates(
    rc: RetrievedContext,
) -> list[tuple[str, float, str, str, str | None, str | None, list[str]]]:
    """Return ordered evidence candidates derived from retrieved context."""

    candidates: list[tuple[str, float, str, str, str | None, str | None, list[str]]] = []

    for decision in rc.historical_decisions:
        score = max(decision.relevance, decision.hybrid_score, decision.recency_bias)
        candidates.append(
            (
                decision.decision_id,
                _percent(score),
                "Historical decision",
                decision.title,
                decision.match_reason or decision.outcome_summary or "Matched on category, brands, and negotiation pattern.",
                decision.date,
                decision.chunk_refs,
            )
        )

    for playbook in rc.playbook_sections:
        candidates.append(
            (
                playbook.chunk_id or playbook.document_id,
                _percent(playbook.relevance),
                "Playbook",
                playbook.section or "Playbook section",
                playbook.applies_because or "Active policy guardrail used in recommendation.",
                None,
                [playbook.chunk_id] if playbook.chunk_id else [],
            )
        )

    for chunk in rc.general_context:
        candidates.append(
            (
                chunk.chunk_id,
                _percent(chunk.relevance),
                _doc_source(chunk.doc_type),
                chunk.title or "Supporting evidence",
                chunk.citation or chunk.content[:180],
                None,
                [chunk.chunk_id],
            )
        )

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates


def build_transparency_from_retrieval(
    session: Session,
    rc: RetrievedContext,
    brief: DraftBrief,
    validation: Validation,
) -> DecisionTransparency:
    candidates = _top_provenance_candidates(rc)
    top_docs: list[RetrievedDocumentInsight] = []

    for idx, candidate in enumerate(candidates[:3]):
        doc_id, score, source, title, explanation, date_label, chunk_refs = candidate
        note: str | None = None
        if chunk_refs:
            stat = session.query(PrecedentStat).filter(PrecedentStat.chunk_id.in_(chunk_refs)).first()
            if stat is not None and stat.used_count:
                note = f"{round(stat.accuracy * 100)}% historical accuracy across {stat.used_count} uses"
        if note is None and source == "Historical decision" and date_label:
            note = f"Historical precedent from {date_label}"
        elif note is None and source == "Playbook":
            note = "Active policy guardrail"
        elif note is None:
            note = "Supporting evidence"

        top_docs.append(
            RetrievedDocumentInsight(
                id=doc_id,
                title=title,
                source=source,
                relevanceScore=score,
                explanation=explanation,
                note=note,
            )
        )

    confidence_reasoning = _confidence_reasoning_from_retrieval(session, rc, brief, validation, top_docs)
    playbook_checks = _playbook_checks_from_retrieval(rc, validation)
    missing_data = _missing_data_from_retrieval(rc, brief, validation)

    return DecisionTransparency(
        retrievedDocuments=top_docs,
        confidenceReasoning=confidence_reasoning,
        playbookChecks=playbook_checks,
        missingData=missing_data,
    )


def build_transparency_from_record(
    session: Session,
    brief_row: DecisionBrief,
    flags: list[Flag] | None = None,
) -> DecisionTransparency:
    stored = (brief_row.brief or {}).get("transparency")
    if stored:
        return DecisionTransparency.model_validate(stored)

    provenance_chunks = (brief_row.brief or {}).get("provenance_chunks") or []
    top_docs = _retrieved_documents_from_persisted_chunks(session, brief_row, provenance_chunks)
    confidence_reasoning = [
        ConfidenceReasoningItem(
            summary=f"Stored brief confidence is {_percent(brief_row.confidence)}%.",
            detail=(
                f"No transparency payload was persisted with this brief, so Lens reconstructed the audit trail "
                f"from the stored provenance chunks and flags."
            ),
        )
    ]
    playbook_checks = _playbook_checks_from_flags(flags or [])
    missing_data = _missing_data_from_brief(brief_row, flags or [])
    return DecisionTransparency(
        retrievedDocuments=top_docs,
        confidenceReasoning=confidence_reasoning,
        playbookChecks=playbook_checks,
        missingData=missing_data,
    )


def _confidence_reasoning_from_retrieval(
    session: Session,
    rc: RetrievedContext,
    brief: DraftBrief,
    validation: Validation,
    top_docs: list[RetrievedDocumentInsight],
) -> list[ConfidenceReasoningItem]:
    items: list[ConfidenceReasoningItem] = []
    checks = validation.confidence_checks
    items.append(
        ConfidenceReasoningItem(
            summary=(
                f"Validator rated evidence as {checks.confidence_rating} with "
                f"{checks.evidence_density:.2f} evidence density."
            ),
            detail=(
                f"Citation validity is {checks.citation_validity:.2f}, with {len(brief.provenance_chunks)} grounded "
                f"provenance chunks across {len(top_docs)} surfaced evidence items."
            ),
        )
    )

    strongest = top_docs[0] if top_docs else None
    if strongest is not None:
        items.append(
            ConfidenceReasoningItem(
                summary=f"Top precedent match is {strongest.title}.",
                detail=(
                    f"{strongest.note or 'A strong historical precedent'} shaped the recommendation, and its "
                    f"retrieved relevance score was {strongest.relevanceScore:.0f}%."
                ),
            )
        )

    if validation.missing_context_alerts:
        items.append(
            ConfidenceReasoningItem(
                summary="Confidence is dampened by missing context.",
                detail="; ".join(f"{alert.type}: {alert.detail}" for alert in validation.missing_context_alerts),
            )
        )

    if not items:
        items.append(
            ConfidenceReasoningItem(
                summary="Confidence is grounded in retrieved precedents.",
                detail="The recommendation was generated from retrieved historical decisions and playbook evidence.",
            )
        )
    return items[:3]


def _playbook_checks_from_retrieval(
    rc: RetrievedContext,
    validation: Validation,
) -> list[PlaybookCheckItem]:
    checks: list[PlaybookCheckItem] = []
    if rc.playbook_sections:
        top = rc.playbook_sections[0]
        checks.append(
            PlaybookCheckItem(
                check="Active playbook guardrails reviewed",
                passed=True,
                detail=top.applies_because or f"Cross-checked against {top.section or 'the active playbook'}",
            )
        )
    else:
        checks.append(
            PlaybookCheckItem(
                check="Active playbook guardrails reviewed",
                passed=False,
                detail="No playbook section was retrieved for this recommendation.",
            )
        )

    if validation.contradiction_flags:
        for flag in validation.contradiction_flags[:2]:
            checks.append(
                PlaybookCheckItem(
                    check=f"Flagged {flag.flag_type.replace('_', ' ')}",
                    passed=False,
                    detail=flag.conflict_reason or flag.rule_quote or "Validator raised a policy conflict.",
                )
            )
    return checks


def _missing_data_from_retrieval(
    rc: RetrievedContext,
    brief: DraftBrief,
    validation: Validation,
) -> list[MissingDataItem]:
    missing: list[MissingDataItem] = []
    for alert in validation.missing_context_alerts:
        missing.append(MissingDataItem(label=alert.type.replace("_", " ").title(), detail=alert.detail))
    for gap in rc.evidence_gaps[:2]:
        missing.append(MissingDataItem(label=gap.type.replace("_", " ").title(), detail=gap.description))
    for gap in brief.evidence_gaps[:1]:
        missing.append(MissingDataItem(label="Brief evidence gap", detail=gap))
    if not missing:
        missing.append(MissingDataItem(label="No major gaps", detail="All required evidence sources were present for this recommendation."))
    return missing[:4]


def _retrieved_documents_from_persisted_chunks(
    session: Session,
    brief_row: DecisionBrief,
    provenance_chunks: Iterable[str],
) -> list[RetrievedDocumentInsight]:
    docs: list[RetrievedDocumentInsight] = []
    stored_precedents = {
        item.get("chunk_id"): item for item in (brief_row.brief or {}).get("precedents", []) if isinstance(item, dict)
    }

    for chunk_id in provenance_chunks:
        chunk = session.get(Chunk, chunk_id)
        if chunk is None:
            precedent = stored_precedents.get(chunk_id)
            if precedent is not None:
                docs.append(
                    RetrievedDocumentInsight(
                        id=chunk_id,
                        title=precedent.get("title", chunk_id),
                        source="Historical decision",
                        relevanceScore=_percent(precedent.get("relevance")),
                        explanation=precedent.get("how_applies") or precedent.get("why_applies") or "Stored precedent",
                        note=precedent.get("outcome") or "Stored precedent",
                    )
                )
            continue

        document = chunk.document
        source = _doc_source(document.doc_type) if document else "Evidence"
        title = document.title if document else chunk_id
        explanation = " ".join(chunk.content.split())[:180]
        note = None
        if document and document.doc_type == "decision":
            note = "Historical decision provenance"
        elif document and document.doc_type in {"playbook", "guideline"}:
            note = "Active policy source"
        docs.append(
            RetrievedDocumentInsight(
                id=chunk_id,
                title=title,
                source=source,
                relevanceScore=0.0,
                explanation=explanation,
                note=note,
            )
        )

    return docs[:3]


def _playbook_checks_from_flags(flags: list[Flag]) -> list[PlaybookCheckItem]:
    if not flags:
        return [
            PlaybookCheckItem(
                check="Policy guardrails reviewed",
                passed=True,
                detail="No contradiction flags were captured on the stored brief.",
            )
        ]

    checks: list[PlaybookCheckItem] = []
    for flag in flags[:3]:
        checks.append(
            PlaybookCheckItem(
                check=f"{flag.flag_type.replace('_', ' ').title()} check",
                passed=flag.severity not in {"high", "critical"},
                detail=flag.conflict_text,
            )
        )
    return checks


def _missing_data_from_brief(brief_row: DecisionBrief, flags: list[Flag]) -> list[MissingDataItem]:
    missing = [
        MissingDataItem(label="Stored transparency", detail="This brief was created before the transparency payload was persisted."),
    ]
    if flags:
        missing.append(
            MissingDataItem(
                label="Policy conflicts",
                detail=f"{len(flags)} flag(s) were recorded, so the decision may need a follow-up review.",
            )
        )
    return missing
