"""Expert routing (docs/expert-agents.md §1): category → agent panel.

A1's `required_expertise` augments the category map; the union, in canonical agent
order, is the panel. The meta-agent always runs.
"""

from app.schemas.context import QueryContext

CATEGORY_AGENTS: dict[str, list[str]] = {
    "procurement": ["supply_chain", "financial", "legal", "operations"],
    "brand": ["brand", "operations", "financial"],
    "product": ["financial", "supply_chain", "brand", "operations"],
    "hr": ["operations", "financial", "legal"],
    "legal": ["legal", "financial"],
    "ops": ["operations", "supply_chain", "financial"],
}

EXPERTISE_TO_AGENT: dict[str, str] = {
    "legal_counsel": "legal",
    "legal": "legal",
    "cfo": "financial",
    "finance": "financial",
    "supply_chain_manager": "supply_chain",
    "supply_chain": "supply_chain",
    "brand_lead": "brand",
    "brand": "brand",
    "ops_head": "operations",
    "ops": "operations",
    "operations": "operations",
}

CANONICAL_ORDER = ["legal", "financial", "supply_chain", "brand", "operations"]

DOMAIN_DOC_TYPES: dict[str, set[str]] = {
    "legal": {"decision", "playbook", "legal", "contract", "compliance", "regulation"},
    "financial": {"decision", "playbook", "financial", "budget", "contract", "pricing"},
    "supply_chain": {"decision", "playbook", "vendor", "contract", "meeting", "logistics", "procurement"},
    "brand": {"brand", "marketing", "packaging", "campaign", "product"},
    "operations": {"playbook", "meeting", "operations", "capacity", "ops"},
}


def panel_for(qc: QueryContext) -> list[str]:
    agents: set[str] = set(CATEGORY_AGENTS.get(qc.category, []))
    for expertise in getattr(qc, "required_expertise", []) or []:
        mapped = EXPERTISE_TO_AGENT.get(str(expertise).lower())
        if mapped:
            agents.add(mapped)
    return [a for a in CANONICAL_ORDER if a in agents]


def domain_doc_types(agent: str) -> set[str]:
    """Doc types that are relevant to an expert agent's domain (context filter)."""
    return DOMAIN_DOC_TYPES.get(agent, set())
