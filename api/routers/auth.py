from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import SESSION_COOKIE, SESSION_LIFETIME, AuthSettings, issue_session, password_matches
from ..dependencies import get_user_name
from ..https import is_https
from ..schemas import LoginRequest, SessionResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_FAILED_LOGIN_DELAY_SECONDS = 1.0


@router.get("/me", response_model=SessionResponse)
def current_session(
        request: Request,
        user_name: Annotated[Optional[str], Depends(get_user_name)],
) -> SessionResponse:
    settings = _settings_of(request)
    if settings.enabled and user_name is None:
        raise HTTPException(status_code=401, detail="Zaloguj się")
    return SessionResponse(name=user_name, auth_enabled=settings.enabled)


@router.post("/login", response_model=SessionResponse)
def login(login_request: LoginRequest, request: Request, response: Response) -> SessionResponse:
    settings = _settings_of(request)
    name = login_request.name.strip()

    if not name:
        raise HTTPException(status_code=422, detail="Podaj imię")
    if not password_matches(login_request.password, settings):
        time.sleep(_FAILED_LOGIN_DELAY_SECONDS)
        raise HTTPException(status_code=401, detail="Złe hasło")

    response.set_cookie(
        SESSION_COOKIE,
        issue_session(name, settings, datetime.now(timezone.utc)),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=is_https(request),
    )
    return SessionResponse(name=name, auth_enabled=settings.enabled)


@router.post("/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE)
    return response


def _settings_of(request: Request) -> AuthSettings:
    return request.state.auth_settings
