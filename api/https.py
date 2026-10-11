from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = frozenset({"/api/health"})


def is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return (forwarded or request.url.scheme) == "https"


def public_url_from_env() -> Optional[str]:
    load_dotenv()
    raw_url = (os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
    return raw_url or None


def install_https_redirect(app: FastAPI, public_url: Optional[str]) -> None:
    if public_url is None:
        return
    if not public_url.startswith("https://"):
        raise ValueError(f"APP_PUBLIC_URL must start with https://, got {public_url}")

    logger.info("Redirecting plain HTTP requests to %s", public_url)

    @app.middleware("http")
    async def redirect_to_https(request: Request, call_next):
        if is_https(request) or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        query = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"{public_url}{request.url.path}{query}", status_code=308)
