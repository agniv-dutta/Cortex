from fastapi import APIRouter

from app.api.v1 import admin, decisions, feedback, ingest, playbooks, portfolio, queries, scenarios, search

api_router = APIRouter()
api_router.include_router(queries.router)
api_router.include_router(decisions.router)
api_router.include_router(feedback.router)
api_router.include_router(search.router)
api_router.include_router(playbooks.router)
api_router.include_router(portfolio.router)
api_router.include_router(scenarios.router)
api_router.include_router(ingest.router)
api_router.include_router(admin.router)
