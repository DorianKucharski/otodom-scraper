from __future__ import annotations

import logging
import unittest
from contextlib import contextmanager
from typing import Optional

from monitoring.log_handler import DatabaseLogHandler


class _FakeSession:
    def __init__(self, sink: list):
        self.__sink = sink
        self.executed = 0

    def add_all(self, rows) -> None:
        self.__sink.extend(rows)

    def execute(self, statement):
        self.executed += 1
        return _FakeResult()


class _FakeResult:
    def scalar_one_or_none(self):
        return None


class _FakeDatabaseManager:
    def __init__(self, failing: bool = False):
        self.rows: list = []
        self.sessions = 0
        self.__failing = failing

    @contextmanager
    def get_session(self):
        self.sessions += 1
        if self.__failing:
            raise RuntimeError("database is down")
        yield _FakeSession(self.rows)


def _record(message: str, level: int = logging.INFO, name: str = "enricher.runner") -> logging.LogRecord:
    return logging.LogRecord(name=name, level=level, pathname=__file__, lineno=1, msg=message, args=(), exc_info=None)


def _handler(database_manager, **overrides) -> DatabaseLogHandler:
    handler = DatabaseLogHandler(
        database_manager=database_manager,
        service="enricher",
        buffer_size=overrides.pop("buffer_size", 3),
        flush_interval_seconds=overrides.pop("flush_interval_seconds", 3600.0),
        **overrides,
    )
    handler.setFormatter(logging.Formatter('%(message)s'))
    return handler


class TestDatabaseLogHandler(unittest.TestCase):

    def test_records_are_buffered_until_the_buffer_fills(self):
        database_manager = _FakeDatabaseManager()
        handler = _handler(database_manager)

        handler.emit(_record("pierwsza"))
        handler.emit(_record("druga"))

        self.assertEqual(0, database_manager.sessions)
        self.assertEqual([], database_manager.rows)

    def test_a_full_buffer_is_written_in_one_session(self):
        database_manager = _FakeDatabaseManager()
        handler = _handler(database_manager)

        for message in ("pierwsza", "druga", "trzecia"):
            handler.emit(_record(message))

        self.assertEqual(1, database_manager.sessions)
        self.assertEqual(["pierwsza", "druga", "trzecia"], [row.message for row in database_manager.rows])

    def test_closing_the_handler_flushes_what_is_left(self):
        database_manager = _FakeDatabaseManager()
        handler = _handler(database_manager)
        handler.emit(_record("ostatnia"))

        handler.close()

        self.assertEqual(["ostatnia"], [row.message for row in database_manager.rows])

    def test_level_and_logger_name_are_stored(self):
        database_manager = _FakeDatabaseManager()
        handler = _handler(database_manager, buffer_size=1)

        handler.emit(_record("uwaga", level=logging.WARNING, name="enricher.image_source"))

        row = database_manager.rows[0]
        self.assertEqual("WARNING", row.level)
        self.assertEqual("enricher.image_source", row.logger_name)
        self.assertEqual("enricher", row.service)

    def test_long_messages_are_truncated(self):
        database_manager = _FakeDatabaseManager()
        handler = _handler(database_manager, buffer_size=1)

        handler.emit(_record("x" * 10_000))

        self.assertEqual(4000, len(database_manager.rows[0].message))

    def test_a_broken_database_does_not_raise_and_pauses_writing(self):
        database_manager = _FakeDatabaseManager(failing=True)
        handler = _handler(database_manager, buffer_size=1)

        handler.emit(_record("pierwsza"))
        sessions_after_failure = database_manager.sessions
        handler.emit(_record("druga"))

        self.assertEqual(1, sessions_after_failure)
        self.assertEqual(sessions_after_failure, database_manager.sessions)

    def test_logging_through_the_root_logger_reaches_the_buffer(self):
        database_manager = _FakeDatabaseManager()
        handler = _handler(database_manager, buffer_size=1)
        logger = logging.getLogger("tests.enricher.sample")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            logger.info("przez logger")
        finally:
            logger.removeHandler(handler)

        self.assertEqual(["przez logger"], [row.message for row in database_manager.rows])


if __name__ == "__main__":
    unittest.main()
