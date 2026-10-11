from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.models import (
    Ad, AdEvaluation, AdEvaluationRequest, AdScreening, AdStatus, EvaluationRequestStatus, EvaluationStatus,
    ScreeningStatus,
)
from database import DatabaseManager
from .runner import EnrichmentRunner
from .selector import AdFilter

logger = logging.getLogger(__name__)

POLL_SECONDS = 10
BATCH_SIZE = 10


@dataclass(frozen=True)
class RequestOutcome:
    status: EvaluationRequestStatus
    message: Optional[str] = None


def request_outcome(
        ad: Optional[Ad],
        screening: Optional[AdScreening],
        evaluation: Optional[AdEvaluation],
) -> RequestOutcome:
    if screening is not None and screening.status == ScreeningStatus.REJECTED:
        return RequestOutcome(EvaluationRequestStatus.REJECTED, screening.rejection_reason)
    if evaluation is not None and evaluation.status in (EvaluationStatus.OK, EvaluationStatus.NO_IMAGES):
        return RequestOutcome(EvaluationRequestStatus.DONE)
    if ad is None or ad.status != AdStatus.ACTIVE:
        return RequestOutcome(EvaluationRequestStatus.FAILED, "Ogłoszenie nie jest już aktywne.")
    if evaluation is not None and evaluation.error_message:
        return RequestOutcome(EvaluationRequestStatus.FAILED, evaluation.error_message)
    if screening is not None and screening.error_message:
        return RequestOutcome(EvaluationRequestStatus.FAILED, screening.error_message)
    return RequestOutcome(EvaluationRequestStatus.FAILED, "Nie udało się ocenić ogłoszenia.")


def pending_request_ids(session: Session, limit: int) -> list[int]:
    return list(session.execute(
        select(AdEvaluationRequest.ad_id)
        .where(AdEvaluationRequest.status == EvaluationRequestStatus.PENDING)
        .order_by(AdEvaluationRequest.requested_at)
        .limit(limit)
    ).scalars())


def requested_spending_usd(session: Session, since: datetime) -> float:
    finished_since = AdEvaluationRequest.finished_at >= since
    local_since = since.astimezone().replace(tzinfo=None)
    screening = session.execute(
        select(func.coalesce(func.sum(AdScreening.cost_usd), 0))
        .join(AdEvaluationRequest, AdEvaluationRequest.ad_id == AdScreening.ad_id)
        .where(finished_since, AdScreening.screened_at >= local_since)
    ).scalar_one()
    evaluation = session.execute(
        select(func.coalesce(func.sum(AdEvaluation.cost_usd), 0))
        .join(AdEvaluationRequest, AdEvaluationRequest.ad_id == AdEvaluation.ad_id)
        .where(finished_since, AdEvaluation.evaluated_at >= local_since)
    ).scalar_one()
    return float(screening) + float(evaluation)


class EvaluationRequestWorker:
    def __init__(
            self,
            database_manager: DatabaseManager,
            runner: EnrichmentRunner,
            daily_budget_usd: Optional[float],
            clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.__database_manager = database_manager
        self.__runner = runner
        self.__daily_budget_usd = daily_budget_usd
        self.__clock = clock
        self.__stop = threading.Event()
        self.__budget_warned = False

    def start(self) -> None:
        threading.Thread(target=self.__loop, name="evaluation-requests", daemon=True).start()

    def stop(self) -> None:
        self.__stop.set()

    def __loop(self) -> None:
        while not self.__stop.wait(POLL_SECONDS):
            try:
                self.process_pending()
            except Exception as error:
                logger.error("Processing evaluation requests failed: %s", error)

    def process_pending(self) -> int:
        with self.__database_manager.get_session() as session:
            ad_ids = pending_request_ids(session, BATCH_SIZE)
            if not ad_ids or self.__is_over_budget(session):
                return 0

        logger.info("Evaluating %s requested ads: %s", len(ad_ids), ad_ids)
        ad_filter = AdFilter(ad_ids=tuple(ad_ids))
        self.__runner.screen(ad_filter).log()
        self.__runner.evaluate(ad_filter).log()
        self.__resolve(ad_ids)
        return len(ad_ids)

    def __is_over_budget(self, session: Session) -> bool:
        if self.__daily_budget_usd is None:
            return False
        spent = requested_spending_usd(session, self.__clock() - timedelta(days=1))
        if spent < self.__daily_budget_usd:
            self.__budget_warned = False
            return False
        if not self.__budget_warned:
            logger.warning(
                "Requested evaluations used up their daily budget of %.2f USD, waiting. "
                "Raise ENRICHER_REQUEST_DAILY_BUDGET_USD to evaluate more.", self.__daily_budget_usd,
            )
            self.__budget_warned = True
        return True

    def __resolve(self, ad_ids: list[int]) -> None:
        with self.__database_manager.get_session() as session:
            for ad_id in ad_ids:
                request = session.get(AdEvaluationRequest, ad_id)
                if request is None:
                    continue
                outcome = request_outcome(
                    session.get(Ad, ad_id), session.get(AdScreening, ad_id), session.get(AdEvaluation, ad_id)
                )
                request.status = outcome.status
                request.message = (outcome.message or None) and outcome.message[:2000]
                request.finished_at = self.__clock()
