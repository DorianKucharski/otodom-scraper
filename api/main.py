from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import ads, facets, saved_searches, stats

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_FRONTEND_DIRECTORY = Path(__file__).parent.parent / "web" / "dist"
_DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173"


def create_app() -> FastAPI:
    app = FastAPI(title="Otodom search API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ads.router)
    app.include_router(facets.router)
    app.include_router(saved_searches.router)
    app.include_router(stats.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    if _FRONTEND_DIRECTORY.is_dir():
        app.mount("/", StaticFiles(directory=_FRONTEND_DIRECTORY, html=True), name="web")
        logger.info("Serving the built frontend from %s", _FRONTEND_DIRECTORY)
    else:
        logger.warning("No built frontend at %s, serving the API only", _FRONTEND_DIRECTORY)

    return app


def _allowed_origins() -> list[str]:
    raw_origins = os.environ.get("API_ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS)
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app = create_app()
