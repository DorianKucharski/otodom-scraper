from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from data.models import ServiceHeartbeat, ServiceStatus
from api.routers.services import _levels_from, _to_status
from monitoring.services import ENRICHER_SERVICE, STALE_AFTER_SECONDS


def _heartbeat(seconds_ago: float, status: ServiceStatus = ServiceStatus.RUNNING) -> ServiceHeartbeat:
    now = datetime.now()
    return ServiceHeartbeat(
        service=ENRICHER_SERVICE,
        status=status,
        phase="ocena ze zdjęciami",
        detail={"przetworzone": 41},
        command="python enrich.py --city=Kraków",
        started_at=now - timedelta(hours=6),
        updated_at=now - timedelta(seconds=seconds_ago),
    )


class TestServiceStatus(unittest.TestCase):

    def test_a_fresh_heartbeat_is_alive(self):
        status = _to_status(ENRICHER_SERVICE, _heartbeat(seconds_ago=5))

        self.assertTrue(status.is_alive)
        self.assertEqual("running", status.status)
        self.assertEqual("Enricher", status.label)

    def test_an_old_heartbeat_is_reported_as_stale(self):
        status = _to_status(ENRICHER_SERVICE, _heartbeat(seconds_ago=STALE_AFTER_SECONDS + 60))

        self.assertFalse(status.is_alive)
        self.assertEqual("stale", status.status)

    def test_a_stale_heartbeat_keeps_the_last_reported_status(self):
        status = _to_status(ENRICHER_SERVICE, _heartbeat(seconds_ago=STALE_AFTER_SECONDS + 60))

        self.assertEqual("running", status.reported_status)

    def test_a_service_that_never_ran_is_unknown(self):
        status = _to_status(ENRICHER_SERVICE, None)

        self.assertEqual("unknown", status.status)
        self.assertFalse(status.is_alive)
        self.assertIsNone(status.updated_at)

    def test_detail_and_phase_are_passed_through(self):
        status = _to_status(ENRICHER_SERVICE, _heartbeat(seconds_ago=1))

        self.assertEqual("ocena ze zdjęciami", status.phase)
        self.assertEqual({"przetworzone": 41}, status.detail)

    def test_seconds_since_update_is_never_negative(self):
        status = _to_status(ENRICHER_SERVICE, _heartbeat(seconds_ago=-30))

        self.assertGreaterEqual(status.seconds_since_update, 0)


class TestLogLevelFilter(unittest.TestCase):

    def test_warning_selects_warning_and_above(self):
        self.assertEqual(["WARNING", "ERROR", "CRITICAL"], _levels_from("WARNING"))

    def test_the_filter_is_case_insensitive(self):
        self.assertEqual(_levels_from("WARNING"), _levels_from("warning"))

    def test_an_unknown_level_keeps_every_level(self):
        self.assertEqual(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], _levels_from("nonsense"))


if __name__ == "__main__":
    unittest.main()
