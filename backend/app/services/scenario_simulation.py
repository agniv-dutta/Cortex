"""Scenario simulation service - "What if" analysis for strategic planning."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ulid import new_id
from app.db.models import Decision, DecisionBrief
from app.providers.llm import LLMProvider
from app.schemas.scenario import (
    FinancialImpact,
    HistoricalAnalogue,
    OutcomeProbability,
    RiskImpact,
    ScenarioRequest,
    ScenarioResponse,
)
from app.services.retriever import Retriever


# Scenario-specific prompt templates
COUNTERFACTUAL_PROMPT = """You are Think9's strategic scenario analyst. Your task is to analyze a "what if" scenario and provide data-driven insights.

SCENARIO QUESTION: {question}
SCENARIO TYPE: {scenario_type}
PARAMETERS: {parameters}
TIME HORIZON: {time_horizon}

CONTEXT:
{context}

ANALYZE the scenario and provide:
1. Financial impacts (magnitude, unit, confidence, drivers)
2. Risk impacts (type, severity, likelihood, description, mitigation)
3. Historical analogues (similar past decisions with outcomes)
4. Outcome probabilities (different possible outcomes with probabilities)
5. Strategic recommendations

Return your analysis as structured JSON matching this schema:
{{
  "summary": "Brief executive summary of the scenario analysis",
  "financial_impacts": [
    {{
      "impact_type": "revenue|cost|margin|cash_flow|working_capital",
      "description": "Clear description of the impact",
      "magnitude": numeric_value,
      "unit": "$|%|basis_points",
      "confidence": 0.0-1.0,
      "drivers": ["list of key drivers"]
    }}
  ],
  "risk_impacts": [
    {{
      "risk_type": "supply|vendor|market|operational|financial",
      "severity": "low|medium|high|critical",
      "likelihood": "low|medium|high",
      "description": "Clear description of the risk",
      "mitigation": "Suggested mitigation strategy or null"
    }}
  ],
  "historical_analogues": [
    {{
      "decision_id": "decision_id_from_context",
      "title": "Title of similar decision",
      "date": "YYYY-MM-DD",
      "similarity": 0.0-1.0,
      "outcome": "success|partial|failure|mixed",
      "key_factors": ["factors that made it similar"],
      "lessons_learned": ["key takeaways"]
    }}
  ],
  "outcome_probabilities": [
    {{
      "outcome": "description of possible outcome",
      "probability": 0.0-1.0,
      "rationale": "why this probability",
      "confidence_interval": [lower_bound, upper_bound] or null
    }}
  ],
  "recommendations": ["strategic recommendations"],
  "assumptions": ["key assumptions made in analysis"],
  "confidence": 0.0-1.0
}}

CRITICAL RULES:
- Base all analysis on the provided CONTEXT from historical decisions
- If insufficient context, state assumptions explicitly
- Probability estimates must be grounded in historical outcomes
- Financial impacts should be realistic ranges, not precise predictions
- Highlight uncertainties and confidence levels clearly
- Never invent historical precedents - use only what's in context
"""


class ScenarioSimulationService:
    """Service for "What if" scenario simulation and analysis."""

    def __init__(self, session: Session, llm_provider: LLMProvider) -> None:
        self.session = session
        self.llm = llm_provider
        self.retriever = Retriever(session)

    def simulate_scenario(self, request: ScenarioRequest) -> ScenarioResponse:
        """Run a scenario simulation analysis."""
        # Retrieve relevant context
        context = self._retrieve_scenario_context(request)
        
        # Build the prompt
        prompt = self._build_counterfactual_prompt(request, context)
        
        # Call LLM for analysis
        analysis = self._run_llm_analysis(prompt)
        
        # Parse and structure the response
        return self._build_scenario_response(request, analysis, context)

    def _retrieve_scenario_context(self, request: ScenarioRequest) -> dict[str, Any]:
        """Retrieve relevant historical decisions and context for the scenario."""
        # Build search query based on scenario type and parameters
        search_query = self._build_search_query(request)
        
        # Retrieve relevant documents
        context_chunks = self.retriever.retrieve(
            query=search_query,
            top_k=20,
            filters={
                "doc_type": ["decision", "contract", "postmortem"],
                "status": ["active"],
            },
        )
        
        # Extract decision IDs from context
        decision_ids = self._extract_decision_ids(context_chunks)
        
        # Fetch full decision records with outcomes
        decisions = self._fetch_decisions_with_outcomes(decision_ids)
        
        return {
            "search_query": search_query,
            "context_chunks": context_chunks,
            "decisions": decisions,
            "chunk_count": len(context_chunks),
            "decision_count": len(decisions),
        }

    def _build_search_query(self, request: ScenarioRequest) -> str:
        """Build a search query based on scenario parameters."""
        query_parts = [request.question]
        
        # Add scenario-specific keywords
        scenario_keywords = {
            "pricing": ["price", "discount", "margin", "revenue", "pricing strategy"],
            "vendor": ["vendor", "supplier", "contract", "negotiation", "renewal"],
            "supply": ["supply", "sourcing", "lead time", "capacity", "inventory"],
            "capacity": ["capacity", "production", "fulfillment", "manufacturing"],
            "financial": ["financial", "cash flow", "working capital", "investment"],
            "strategic": ["strategic", "positioning", "market", "competition"],
        }
        
        keywords = scenario_keywords.get(request.scenario_type, [])
        query_parts.extend(keywords)
        
        # Add parameter-specific terms
        for key, value in request.parameters.items():
            if isinstance(value, str):
                query_parts.append(value)
            elif isinstance(value, (int, float)):
                query_parts.append(str(value))
        
        # Add brand filters if specified
        if request.brands:
            query_parts.extend(request.brands)
        
        return " ".join(query_parts)

    def _extract_decision_ids(self, context_chunks: list[dict]) -> list[str]:
        """Extract decision IDs from retrieved context chunks."""
        decision_ids = set()
        for chunk in context_chunks:
            if "document_id" in chunk:
                decision_ids.add(chunk["document_id"])
            if "decision_id" in chunk:
                decision_ids.add(chunk["decision_id"])
        return list(decision_ids)

    def _fetch_decisions_with_outcomes(self, decision_ids: list[str]) -> list[dict]:
        """Fetch decision records with their outcomes."""
        if not decision_ids:
            return []
        
        decisions = []
        for decision_id in decision_ids:
            decision = self.session.get(Decision, decision_id)
            if decision:
                # Fetch brief if available
                brief = self.session.execute(
                    select(DecisionBrief)
                    .where(DecisionBrief.decision_id == decision_id)
                    .order_by(DecisionBrief.created_at.desc())
                ).scalar_one_or_none()
                
                decisions.append({
                    "id": decision.id,
                    "statement": decision.statement,
                    "category": decision.category,
                    "decision_class": decision.decision_class,
                    "status": decision.status,
                    "brands": decision.brands,
                    "created_at": decision.created_at.isoformat() if decision.created_at else None,
                    "brief": brief.brief if brief else None,
                    "confidence": brief.confidence if brief else None,
                })
        
        return decisions

    def _build_counterfactual_prompt(self, request: ScenarioRequest, context: dict) -> str:
        """Build the counterfactual reasoning prompt."""
        # Format context for the prompt
        context_text = self._format_context_for_prompt(context)
        
        prompt = COUNTERFACTUAL_PROMPT.format(
            question=request.question,
            scenario_type=request.scenario_type,
            parameters=request.parameters,
            time_horizon=request.time_horizon,
            context=context_text,
        )
        
        return prompt

    def _format_context_for_prompt(self, context: dict) -> str:
        """Format retrieved context for the LLM prompt."""
        parts = [f"Retrieved {context['chunk_count']} context chunks from {context['decision_count']} historical decisions:\n"]
        
        for decision in context["decisions"][:10]:  # Limit to top 10 for context window
            parts.append(f"\nDECISION: {decision['id']}")
            parts.append(f"Statement: {decision['statement']}")
            parts.append(f"Category: {decision['category']}")
            parts.append(f"Class: {decision['decision_class']}")
            parts.append(f"Status: {decision['status']}")
            parts.append(f"Brands: {', '.join(decision['brands'] or [])}")
            if decision['brief']:
                parts.append(f"Brief confidence: {decision['confidence']}")
        
        return "\n".join(parts)

    def _run_llm_analysis(self, prompt: str) -> dict:
        """Run the LLM analysis for scenario simulation."""
        try:
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.3,  # Lower temperature for more analytical responses
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            
            # Parse JSON response
            import json
            analysis = json.loads(response)
            return analysis
        except Exception as e:
            # Fallback to basic structure if LLM fails
            return {
                "summary": f"Analysis failed: {str(e)}",
                "financial_impacts": [],
                "risk_impacts": [],
                "historical_analogues": [],
                "outcome_probabilities": [],
                "recommendations": [],
                "assumptions": ["LLM analysis failed"],
                "confidence": 0.0,
            }

    def _build_scenario_response(
        self, request: ScenarioRequest, analysis: dict, context: dict
    ) -> ScenarioResponse:
        """Build the structured scenario response from LLM analysis."""
        # Parse financial impacts
        financial_impacts = [
            FinancialImpact(**impact) for impact in analysis.get("financial_impacts", [])
        ]
        
        # Parse risk impacts
        risk_impacts = [
            RiskImpact(**risk) for risk in analysis.get("risk_impacts", [])
        ]
        
        # Parse historical analogues
        historical_analogues = [
            HistoricalAnalogue(**analogue) for analogue in analysis.get("historical_analogues", [])
        ]
        
        # Parse outcome probabilities
        outcome_probabilities = [
            OutcomeProbability(**prob) for prob in analysis.get("outcome_probabilities", [])
        ]
        
        # Build response
        response = ScenarioResponse(
            scenario_id=new_id("scn"),
            question=request.question,
            scenario_type=request.scenario_type,
            summary=analysis.get("summary", ""),
            financial_impacts=financial_impacts,
            risk_impacts=risk_impacts,
            historical_analogues=historical_analogues,
            outcome_probabilities=outcome_probabilities,
            recommendations=analysis.get("recommendations", []),
            confidence=analysis.get("confidence", 0.5),
            assumptions=analysis.get("assumptions", []),
            data_sources=[f"{context['decision_count']} historical decisions"],
            model_info={
                "llm_model": self.llm.model_name,
                "context_chunks_used": context["chunk_count"],
                "decisions_analyzed": context["decision_count"],
            },
        )
        
        return response

    def _calculate_financial_impact(
        self, scenario_type: str, parameters: dict, context: dict
    ) -> list[FinancialImpact]:
        """Calculate financial impacts based on scenario parameters."""
        # This would integrate with financial models if available
        # For now, provide basic heuristic calculations
        impacts = []
        
        if scenario_type == "pricing":
            price_change = parameters.get("price_change_percent", 0)
            if price_change:
                impacts.append(
                    FinancialImpact(
                        impact_type="revenue",
                        description=f"Revenue impact from {price_change}% price change",
                        magnitude=price_change,
                        unit="%",
                        confidence=0.6,
                        drivers=["price elasticity", "volume sensitivity"],
                    )
                )
        
        elif scenario_type == "vendor":
            moq_change = parameters.get("moq_quantity", 0)
            if moq_change:
                impacts.append(
                    FinancialImpact(
                        impact_type="working_capital",
                        description=f"Working capital impact from MOQ change to {moq_change}",
                        magnitude=moq_change * 0.1,  # Heuristic
                        unit="$",
                        confidence=0.5,
                        drivers=["inventory holding cost", "cash flow timing"],
                    )
                )
        
        return impacts

    def _estimate_outcome_probability(
        self, scenario_type: str, historical_outcomes: list[dict]
    ) -> list[OutcomeProbability]:
        """Estimate outcome probabilities based on historical precedents."""
        if not historical_outcomes:
            return []
        
        # Count outcome types
        outcome_counts = {}
        for outcome in historical_outcomes:
            outcome_type = outcome.get("status", "unknown")
            outcome_counts[outcome_type] = outcome_counts.get(outcome_type, 0) + 1
        
        total = len(historical_outcomes)
        probabilities = []
        
        for outcome_type, count in outcome_counts.items():
            probability = count / total
            probabilities.append(
                OutcomeProbability(
                    outcome=outcome_type,
                    probability=probability,
                    rationale=f"Based on {count} similar historical decisions out of {total}",
                    confidence_interval=[max(0, probability - 0.2), min(1, probability + 0.2)],
                )
            )
        
        return probabilities
