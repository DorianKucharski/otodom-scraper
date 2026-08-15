from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select

from data.models import AdEvaluation, AdScreening
from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailySpending:
    screening_usd: float
    evaluation_usd: float

    @property
    def total_usd(self) -> float:
        return self.screening_usd + self.evaluation_usd


class DailyBudget:
    def __init__(self, database_manager: DatabaseManager, limit_usd: Optional[float]):
        self.__database_manager = database_manager
        self.__limit_usd = limit_usd

    @property
    def limit_usd(self) -> Optional[float]:
        return self.__limit_usd

    def spending_today(self) -> DailySpending:
        since = datetime.now() - timedelta(days=1)

        with self.__database_manager.get_session() as session:
            screening = session.execute(
                select(func.coalesce(func.sum(AdScreening.cost_usd), 0)).where(AdScreening.screened_at >= since)
            ).scalar_one()
            evaluation = session.execute(
                select(func.coalesce(func.sum(AdEvaluation.cost_usd), 0)).where(AdEvaluation.evaluated_at >= since)
            ).scalar_one()

        return DailySpending(screening_usd=float(screening), evaluation_usd=float(evaluation))

    def remaining_usd(self) -> Optional[float]:
        if self.__limit_usd is None:
            return None
        return max(self.__limit_usd - self.spending_today().total_usd, 0.0)

    def is_exhausted(self) -> bool:
        remaining = self.remaining_usd()
        if remaining is None:
            return False

        if remaining <= 0:
            logger.warning(
                "Daily budget of %.2f USD is used up, skipping this cycle. "
                "Raise ENRICHER_DAILY_BUDGET_USD or wait for the window to roll over.",
                self.__limit_usd,
            )
            return True

        return False
