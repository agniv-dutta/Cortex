"""Scenario simulation endpoints — "What if" analysis for strategic planning."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.providers.llm import get_llm_provider
from app.schemas.scenario import ScenarioRequest, ScenarioResponse
from app.services.scenario_simulation import ScenarioSimulationService

router = APIRouter(tags=["scenarios"])


@router.post("/scenarios/simulate", response_model=ScenarioResponse)
def simulate_scenario(
    request: ScenarioRequest,
    db: Session = Depends(get_db),
) -> ScenarioResponse:
    """Run a 'What if' scenario simulation for strategic planning.
    
    Examples:
    - "If we increase Vendor X's MOQ to 50K, what's our exposure?"
    - "What if we raise prices by 15% across all brands?"
    - "What if we switch to Supplier Y for raw materials?"
    
    The system simulates impact on cash flow, supply risk, margin,
    shows historical precedents where similar changes occurred,
    and estimates outcome probability.
    """
    llm_provider = get_llm_provider()
    service = ScenarioSimulationService(db, llm_provider)
    return service.simulate_scenario(request)
