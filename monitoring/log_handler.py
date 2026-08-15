from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from time import monotonic
from typing import Optional

from sqlalchemy import delete, func, select

from data.models import ServiceLog
from database import DatabaseManager

DEFAULT_RETAINED_ROWS = 2000
DEFAULT_BUFFER_SIZE = 20
DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0
_TRIM_EVERY_FLUSHES = 20
_MAX_MESSAGE_LENGTH = 4000
_RETRY_AFTER_FAILURE_SECONDS = 60.0


class DatabaseLogHandler(logging.Handler):
    def __init__(
            self,
            database_manager: DatabaseManager,
            service: str,
            level: int = logging.INFO,
            buffer_size: int = DEFAULT_BUFFER_SIZE,
            flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
            retained_rows: int = DEFAULT_RETAINED_ROWS,
    ):
        super().__init__(level=level)
        self.__database_manager = database_manager
        self.__service = service
        self.__buffer_size = buffer_size
        self.__flush_interval_seconds = flush_interval_seconds
        self.__retained_rows = retained_rows
        self.__buffer: list[ServiceLog] = []
        self.__buffer_lock = threading.Lock()
        self.__last_flush = monotonic()
        self.__flushes_since_trim = 0
        self.__silenced_until = 0.0

    def emit(self, record: logging.LogRecord) -> None:
        if monotonic() < self.__silenced_until:
            return

        try:
            entry = self.__to_entry(record)
        except Exception:
            self.handleError(record)
            return

        with self.__buffer_lock:
            self.__buffer.append(entry)
            should_flush = (
                    len(self.__buffer) >= self.__buffer_size
                    or monotonic() - self.__last_flush >= self.__flush_interval_seconds
            )

        if should_flush:
            self.flush()

    def flush(self) -> None:
        with self.__buffer_lock:
            pending = self.__buffer
            self.__buffer = []
            self.__last_flush = monotonic()
            self.__flushes_since_trim += 1
            should_trim = self.__flushes_since_trim >= _TRIM_EVERY_FLUSHES
            if should_trim:
                self.__flushes_since_trim = 0

        if not pending:
            return

        try:
            with self.__database_manager.get_session() as session:
                session.add_all(pending)
                if should_trim:
                    self.__trim(session)
        except Exception as error:
            self.__silenced_until = monotonic() + _RETRY_AFTER_FAILURE_SECONDS
            print(
                f"DatabaseLogHandler dropped {len(pending)} rows and pauses for "
                f"{_RETRY_AFTER_FAILURE_SECONDS:.0f}s: {error}",
                file=sys.stderr,
            )

    def close(self) -> None:
        self.flush()
        super().close()

    def __to_entry(self, record: logging.LogRecord) -> ServiceLog:
        return ServiceLog(
            service=self.__service,
            level=record.levelname,
            logger_name=record.name[:120],
            message=self.format(record)[:_MAX_MESSAGE_LENGTH],
            logged_at=datetime.fromtimestamp(record.created),
        )

    def __trim(self, session) -> None:
        newest_id = session.execute(
            select(func.max(ServiceLog.id)).where(ServiceLog.service == self.__service)
        ).scalar_one_or_none()

        if newest_id is None:
            return

        session.execute(delete(ServiceLog).where(
            ServiceLog.service == self.__service,
            ServiceLog.id <= newest_id - self.__retained_rows,
        ))


def attach_database_logging(
        database_manager: DatabaseManager,
        service: str,
        level: int = logging.INFO,
        retained_rows: int = DEFAULT_RETAINED_ROWS,
) -> Optional[DatabaseLogHandler]:
    handler = DatabaseLogHandler(
        database_manager=database_manager,
        service=service,
        level=level,
        retained_rows=retained_rows,
    )
    handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(handler)
    return handler
