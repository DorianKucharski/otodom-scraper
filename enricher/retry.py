from __future__ import annotations

import logging
from time import sleep
from typing import Callable, TypeVar

from .llm.client import LlmPermanentError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def call_with_retry(action: Callable[[], T], max_tries: int, pause_seconds: int, description: str) -> T:
    last_error: Exception | None = None

    for attempt in range(1, max_tries + 1):
        try:
            return action()
        except LlmPermanentError as error:
            logger.error("%s failed permanently, not retrying: %s", description, error)
            raise
        except Exception as error:
            last_error = error
            logger.warning("%s failed (attempt %s of %s): %s", description, attempt, max_tries, error)
            if attempt < max_tries:
                sleep(pause_seconds)

    raise last_error
