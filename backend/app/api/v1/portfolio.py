"""POST /v1/portfolio/intelligence — cross-brand aggregation and triggers."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.portfolio import PortfolioIntelligenceRequest, PortfolioIntelligenceResponse
from app.services.decision_aggregation import DecisionAggregationService
from app.services.portfolio import PortfolioIntelligenceService

router = APIRouter(tags=["portfolio"])


@router.post("/portfolio/intelligence", response_model=PortfolioIntelligenceResponse)
def generate_portfolio_intelligence(
    body: PortfolioIntelligenceRequest,
    db: Session = Depends(get_db),
) -> PortfolioIntelligenceResponse:
    service = PortfolioIntelligenceService(db)
    return service.generate_report(body)


@router.get("/portfolio/decisions/scan", response_model=PortfolioIntelligenceResponse)
def scan_decisions_for_patterns(
    since_days: int = Query(default=30, ge=1, le=365, description="Days to look back for decisions"),
    brands: Optional[list[str]] = Query(default=None, description="Filter by brands"),
    min_brands: int = Query(default=2, ge=2, le=50, description="Minimum brands to form a cluster"),
    min_score: float = Query(default=0.6, ge=0.0, le=1.0, description="Minimum cluster score"),
    db: Session = Depends(get_db),
) -> PortfolioIntelligenceResponse:
    """Scan recent decisions for multi-brand patterns and consolidation opportunities."""
    service = DecisionAggregationService(db)
    return service.scan_decisions(
        since_days=since_days,
        brands=brands,
        min_brands=min_brands,
        min_score=min_score,
        report_type="ad_hoc",
    )


@router.get("/portfolio/decisions/monthly-report", response_model=PortfolioIntelligenceResponse)
def generate_monthly_decision_report(
    month: Optional[int] = Query(default=None, ge=1, le=12, description="Month (1-12), defaults to current"),
    year: Optional[int] = Query(default=None, ge=2020, le=2030, description="Year, defaults to current"),
    db: Session = Depends(get_db),
) -> PortfolioIntelligenceResponse:
    """Generate monthly cross-portfolio value report from decisions."""
    service = DecisionAggregationService(db)
    return service.generate_monthly_report(month=month, year=year)
