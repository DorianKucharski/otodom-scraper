from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RefreshingCache(Generic[T]):

    def __init__(
            self,
            load: Callable[[], T],
            max_age_seconds: float,
            clock: Callable[[], float] = time.monotonic,
            spawn: Callable[[Callable[[], None]], None] = lambda target: threading.Thread(
                target=target, daemon=True
            ).start(),
    ):
        self.__load = load
        self.__max_age_seconds = max_age_seconds
        self.__clock = clock
        self.__spawn = spawn
        self.__lock = threading.Lock()
        self.__value: Optional[T] = None
        self.__loaded_at: Optional[float] = None
        self.__refreshing = False

    def get(self) -> T:
        with self.__lock:
            value, loaded_at = self.__value, self.__loaded_at

        if value is None:
            return self.__refresh()
        if self.__clock() - loaded_at > self.__max_age_seconds:
            self.refresh_in_background()
        return value

    def refresh_in_background(self) -> None:
        with self.__lock:
            if self.__refreshing:
                return
            self.__refreshing = True
        self.__spawn(self.__refresh_quietly)

    def __refresh_quietly(self) -> None:
        try:
            self.__refresh()
        except Exception:
            logger.exception("Background cache refresh failed, keeping the previous value")
        finally:
            with self.__lock:
                self.__refreshing = False

    def __refresh(self) -> T:
        value = self.__load()
        with self.__lock:
            self.__value = value
            self.__loaded_at = self.__clock()
        return value
