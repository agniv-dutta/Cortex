"""FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Think9 Decision Intelligence",
        version=APP_VERSION,
        description="Institutional-knowledge retrieval + grounded decision briefs.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": APP_VERSION}

    return app


app = create_app()
