from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import Ad, AdEvaluationRequest, EvaluationRequestStatus
from llm.factory import build_llm_client
from ..assistant.calls import AssistantBudgetExceeded, AssistantLlm, spent_today_usd
from ..assistant.config import AssistantConfig
from ..assistant.service import Assistant
from ..dependencies import get_database_manager, get_session, get_user_name
from ..schemas import (
    AssistantInterpretRequest, AssistantInterpretResponse, AssistantRankRequest, AssistantRankResponse,
    AssistantStatusResponse, EvaluationRequestResponse, EvaluationRequestsRequest,
)
from .facets import facets_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@lru_cache(maxsize=1)
def _assistant() -> tuple[Optional[Assistant], Optional[str]]:
    try:
        config = AssistantConfig.from_env()
    except ValueError as error:
        logger.warning("Assistant disabled: %s", error)
        return None, str(error)
    llm = AssistantLlm(get_database_manager(), build_llm_client(config.llm), config.daily_budget_usd)
    return Assistant(config, llm), None


def _require_assistant() -> Assistant:
    assistant, reason = _assistant()
    if assistant is None:
        raise HTTPException(status_code=503, detail=f"Asystent jest wyłączony: {reason}")
    return assistant


@router.get("", response_model=AssistantStatusResponse)
def assistant_status(session: Annotated[Session, Depends(get_session)]) -> AssistantStatusResponse:
    assistant, reason = _assistant()
    if assistant is None:
        return AssistantStatusResponse(enabled=False, reason=reason)
    return AssistantStatusResponse(
        enabled=True,
        spent_today_usd=round(spent_today_usd(session), 4),
        daily_budget_usd=assistant.daily_budget_usd,
    )


@router.post("/interpret", response_model=AssistantInterpretResponse)
def interpret(
        request: AssistantInterpretRequest,
        user_name: Annotated[Optional[str], Depends(get_user_name)],
) -> AssistantInterpretResponse:
    assistant = _require_assistant()
    try:
        return assistant.interpret(request.message, request.history, request.previous, facets_cache.get(), user_name)
    except AssistantBudgetExceeded as error:
        raise HTTPException(status_code=429, detail=str(error))
    except Exception as error:
        logger.error("Assistant interpretation failed: %s", error)
        raise HTTPException(status_code=502, detail=f"Model nie odpowiedział poprawnie: {error}")


@router.post("/rank", response_model=AssistantRankResponse)
def rank(
        request: AssistantRankRequest,
        session: Annotated[Session, Depends(get_session)],
        user_name: Annotated[Optional[str], Depends(get_user_name)],
) -> AssistantRankResponse:
    assistant = _require_assistant()
    try:
        return assistant.rank(session, request.message, request.history, request.plan, user_name)
    except AssistantBudgetExceeded as error:
        raise HTTPException(status_code=429, detail=str(error))
    except Exception as error:
        logger.error("Assistant ranking failed: %s", error)
        raise HTTPException(status_code=502, detail=f"Model nie odpowiedział poprawnie: {error}")


@router.post("/evaluation-requests", response_model=list[EvaluationRequestResponse])
def request_evaluations(
        request: EvaluationRequestsRequest,
        session: Annotated[Session, Depends(get_session)],
        user_name: Annotated[Optional[str], Depends(get_user_name)],
) -> list[EvaluationRequestResponse]:
    known_ids = set(session.execute(select(Ad.id).where(Ad.id.in_(request.ad_ids))).scalars())
    now = datetime.now(timezone.utc)
    for ad_id in known_ids:
        existing = session.get(AdEvaluationRequest, ad_id)
        if existing is None:
            session.add(AdEvaluationRequest(
                ad_id=ad_id, status=EvaluationRequestStatus.PENDING, requested_by=user_name, requested_at=now,
            ))
        elif existing.status != EvaluationRequestStatus.PENDING:
            existing.status = EvaluationRequestStatus.PENDING
            existing.requested_by = user_name
            existing.requested_at = now
            existing.finished_at = None
            existing.message = None
    session.flush()
    return _requests_for(session, sorted(known_ids))


@router.get("/evaluation-requests", response_model=list[EvaluationRequestResponse])
def evaluation_requests(
        session: Annotated[Session, Depends(get_session)],
        ids: Annotated[list[int], Query(max_length=50)] = [],
) -> list[EvaluationRequestResponse]:
    return _requests_for(session, ids)


def _requests_for(session: Session, ad_ids: list[int]) -> list[EvaluationRequestResponse]:
    if not ad_ids:
        return []
    rows = session.execute(select(AdEvaluationRequest).where(AdEvaluationRequest.ad_id.in_(ad_ids))).scalars()
    return [
        EvaluationRequestResponse(
            ad_id=row.ad_id,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            message=row.message,
            requested_at=row.requested_at,
            finished_at=row.finished_at,
        )
        for row in rows
    ]
