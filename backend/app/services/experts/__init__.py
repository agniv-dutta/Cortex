"""Expert-agent layer (docs/expert-agents.md): routing, parallel panel, meta synthesis."""

from app.services.experts.agents import ExpertAgent, run_expert_panel
from app.services.experts.meta import (
    MetaAgent,
    detect_conflicts,
    hard_constraints_conflict,
    merge_risks,
    resolve,
)
from app.services.experts.routing import panel_for

__all__ = [
    "ExpertAgent",
    "MetaAgent",
    "detect_conflicts",
    "hard_constraints_conflict",
    "merge_risks",
    "panel_for",
    "resolve",
    "run_expert_panel",
]
