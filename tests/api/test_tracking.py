from __future__ import annotations

import unittest
from datetime import datetime, timezone

from api.schemas import TrackingEventRequest
from api.tracking import TrackingEventError, record_event
from data.models import Ad, TrackingStatus

_NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
_VIEWING = datetime(2026, 10, 14, 18, 30)


def _ad() -> Ad:
    return Ad(id=42, price_value=650000)


def _event(**fields) -> TrackingEventRequest:
    return TrackingEventRequest(**fields)


class TestRecordEvent(unittest.TestCase):

    def test_the_first_event_starts_tracking_with_the_current_price(self):
        tracking = record_event(None, _ad(), _event(status=TrackingStatus.SHORTLISTED), "Dorian", _NOW)

        self.assertEqual(TrackingStatus.SHORTLISTED, tracking.status)
        self.assertEqual(650000, tracking.price_at_save)
        self.assertEqual(1, len(tracking.events))
        self.assertEqual("Dorian", tracking.events[0].author)

    def test_the_first_event_must_set_a_status(self):
        with self.assertRaises(TrackingEventError):
            record_event(None, _ad(), _event(comment="ładne"), "Dorian", _NOW)

    def test_an_event_needs_a_status_or_a_comment(self):
        tracking = record_event(None, _ad(), _event(status=TrackingStatus.TO_CALL), "Dorian", _NOW)

        with self.assertRaises(TrackingEventError):
            record_event(tracking, _ad(), _event(comment="   "), "Dorian", _NOW)

    def test_a_viewing_needs_a_date(self):
        with self.assertRaises(TrackingEventError):
            record_event(None, _ad(), _event(status=TrackingStatus.VIEWING_SCHEDULED), "Dorian", _NOW)

    def test_a_viewing_keeps_the_wall_clock_time(self):
        tracking = record_event(
            None, _ad(),
            _event(status=TrackingStatus.VIEWING_SCHEDULED, viewing_at="2026-10-14T18:30:00+02:00"),
            "Dorian", _NOW,
        )

        self.assertEqual(_VIEWING, tracking.viewing_at)

    def test_a_comment_alone_keeps_the_status_and_becomes_the_last_comment(self):
        tracking = record_event(None, _ad(), _event(status=TrackingStatus.CONTACTED), "Dorian", _NOW)

        record_event(tracking, _ad(), _event(comment=" oddzwonią jutro "), "Żona", _NOW)

        self.assertEqual(TrackingStatus.CONTACTED, tracking.status)
        self.assertEqual("oddzwonią jutro", tracking.last_comment)
        self.assertEqual("Żona", tracking.updated_by)
        self.assertEqual(2, len(tracking.events))
        self.assertIsNone(tracking.events[1].status)

    def test_a_later_status_keeps_the_viewing_date(self):
        tracking = record_event(
            None, _ad(), _event(status=TrackingStatus.VIEWING_SCHEDULED, viewing_at=_VIEWING), "Dorian", _NOW
        )

        record_event(tracking, _ad(), _event(status=TrackingStatus.VIEWED, rating=4), "Dorian", _NOW)

        self.assertEqual(_VIEWING, tracking.viewing_at)
        self.assertEqual(4, tracking.rating)

    def test_the_price_at_save_is_not_overwritten(self):
        tracking = record_event(None, _ad(), _event(status=TrackingStatus.SHORTLISTED), "Dorian", _NOW)
        cheaper = Ad(id=42, price_value=600000)

        record_event(tracking, cheaper, _event(status=TrackingStatus.OFFER_MADE, offer_amount=580000), "Dorian", _NOW)

        self.assertEqual(650000, tracking.price_at_save)
        self.assertEqual(580000, tracking.offer_amount)


if __name__ == "__main__":
    unittest.main()
