from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.models import AssistantCall, AssistantCallKind
from database import DatabaseManager
from llm.client import LlmClient, LlmRequest, LlmResponse
from llm.pricing import cost_usd_for
from llm.retry import call_with_retry

logger = logging.getLogger(__name__)

_MAX_TRIES = 2
_RETRY_PAUSE_SECONDS = 3


class AssistantBudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class AssistantCompletion:
    payload: dict
    cost_usd: float


def spent_today_usd(session: Session) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return float(session.execute(
        select(func.coalesce(func.sum(AssistantCall.cost_usd), 0)).where(AssistantCall.created_at >= since)
    ).scalar_one())


class AssistantLlm:
    def __init__(self, database_manager: DatabaseManager, client: LlmClient, daily_budget_usd: float):
        self.__database_manager = database_manager
        self.__client = client
        self.__daily_budget_usd = daily_budget_usd

    @property
    def daily_budget_usd(self) -> float:
        return self.__daily_budget_usd

    def complete(
            self,
            kind: AssistantCallKind,
            request: LlmRequest,
            author: Optional[str],
            message: str,
            logged_request: dict,
    ) -> AssistantCompletion:
        with self.__database_manager.get_session() as session:
            if spent_today_usd(session) >= self.__daily_budget_usd:
                raise AssistantBudgetExceeded(
                    f"Asystent wykorzystał dzienny budżet {self.__daily_budget_usd:.2f} USD. "
                    "Spróbuj jutro albo podnieś ASSISTANT_DAILY_BUDGET_USD."
                )

        try:
            response = call_with_retry(
                lambda: self.__client.complete(request),
                max_tries=_MAX_TRIES,
                pause_seconds=_RETRY_PAUSE_SECONDS,
                description=f"Assistant {kind.value}",
            )
        except Exception as error:
            self.__record(kind, request.model, author, message, logged_request, None, None, str(error))
            raise

        cost = _cost_of(response)
        self.__record(kind, response.model, author, message, logged_request, response, cost, None)
        return AssistantCompletion(payload=response.payload, cost_usd=cost or 0.0)

    def __record(
            self,
            kind: AssistantCallKind,
            model: str,
            author: Optional[str],
            message: str,
            logged_request: dict,
            response: Optional[LlmResponse],
            cost: Optional[float],
            error: Optional[str],
    ) -> None:
        try:
            with self.__database_manager.get_session() as session:
                session.add(AssistantCall(
                    kind=kind,
                    author=author,
                    message=message,
                    request=logged_request,
                    response=response.payload if response else None,
                    model=model,
                    input_tokens=(response.input_tokens + response.cache_read_tokens
                                  + response.cache_write_tokens) if response else 0,
                    output_tokens=response.output_tokens if response else 0,
                    cost_usd=cost,
                    error_message=error[:2000] if error else None,
                ))
        except Exception as write_error:
            logger.error("Could not record assistant call: %s", write_error)


def _cost_of(response: LlmResponse) -> Optional[float]:
    return cost_usd_for(
        response.model,
        response.input_tokens,
        response.output_tokens,
        response.cache_read_tokens,
        response.cache_write_tokens,
    )
