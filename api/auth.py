from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

SESSION_COOKIE = "otodom_session"
SESSION_LIFETIME = timedelta(days=365)
MAX_NAME_LENGTH = 50

_PUBLIC_PATHS = frozenset({"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/me"})
_PROTECTED_PREFIXES = ("/api/", "/docs", "/redoc", "/openapi.json")


@dataclass(frozen=True)
class AuthSettings:
    password: Optional[str]

    @property
    def enabled(self) -> bool:
        return bool(self.password)

    @classmethod
    def from_env(cls) -> AuthSettings:
        load_dotenv()
        return cls(password=os.environ.get("APP_PASSWORD") or None)


def password_matches(candidate: str, settings: AuthSettings) -> bool:
    if not settings.enabled:
        return True
    return hmac.compare_digest(candidate.encode(), settings.password.encode())


def issue_session(name: str, settings: AuthSettings, issued_at: datetime) -> str:
    body = json.dumps({"name": name, "iat": int(issued_at.timestamp())}, ensure_ascii=False)
    payload = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"{payload}.{_signature(payload, settings)}"


def read_session(token: Optional[str], settings: AuthSettings, now: datetime) -> Optional[str]:
    if not token or "." not in token:
        return None

    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _signature(payload, settings)):
        return None

    try:
        body = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        name = str(body["name"])
        issued_at = datetime.fromtimestamp(int(body["iat"]), tz=timezone.utc)
    except (ValueError, KeyError, TypeError):
        return None

    if now - issued_at > SESSION_LIFETIME or not name:
        return None
    return name


def install_auth(app: FastAPI, settings: AuthSettings) -> None:
    if settings.enabled:
        logger.info("Password protection is on")
    else:
        logger.warning("APP_PASSWORD is not set, the API is open to anyone who can reach it")

    @app.middleware("http")
    async def require_session(request: Request, call_next):
        request.state.auth_settings = settings
        request.state.user_name = read_session(
            request.cookies.get(SESSION_COOKIE), settings, datetime.now(timezone.utc)
        )

        if settings.enabled and request.state.user_name is None and _is_protected(request.url.path):
            return JSONResponse(status_code=401, content={"detail": "Zaloguj się"})

        return await call_next(request)


def _is_protected(path: str) -> bool:
    return path not in _PUBLIC_PATHS and path.startswith(_PROTECTED_PREFIXES)


def _signature(payload: str, settings: AuthSettings) -> str:
    key = hashlib.sha256(f"otodom-session:{settings.password or ''}".encode()).digest()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
