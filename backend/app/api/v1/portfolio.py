"""POST /v1/portfolio/intelligence â€” cross-brand aggregation and triggers."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.portfolio import PortfolioIntelligenceRequest, PortfolioIntelligenceResponse
from app.services.portfolio import PortfolioIntelligenceService

router = APIRouter(tags=["portfolio"])


@router.post("/portfolio/intelligence", response_model=PortfolioIntelligenceResponse)
def generate_portfolio_intelligence(
    body: PortfolioIntelligenceRequest,
    db: Session = Depends(get_db),
) -> PortfolioIntelligenceResponse:
    service = PortfolioIntelligenceService(db)
    return service.generate_report(body)

