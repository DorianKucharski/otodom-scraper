from __future__ import annotations

import unittest
from datetime import datetime

from data.models import AdStatus
from data.price_history import PriceState, price_observation, price_state_of
from tests.enricher.ad_builder import AdBuilder

_NOW = datetime(2026, 10, 24, 20, 0)


class TestPriceObservation(unittest.TestCase):

    def test_a_new_ad_records_its_first_price(self):
        ad = AdBuilder().with_price(1_099_000).build()

        observation = price_observation(ad, None, _NOW)

        self.assertEqual(1_099_000, observation.price_value)
        self.assertEqual("active", observation.status)
        self.assertEqual(_NOW, observation.observed_at)

    def test_an_unchanged_ad_records_nothing(self):
        ad = AdBuilder().build()

        self.assertIsNone(price_observation(ad, price_state_of(ad), _NOW))

    def test_a_price_change_is_recorded(self):
        ad = AdBuilder().with_price(1_029_000).build()
        previous = PriceState(price_value=1_079_000, area_value=60.0, status="active")

        self.assertEqual(1_029_000, price_observation(ad, previous, _NOW).price_value)

    def test_a_status_change_is_recorded(self):
        ad = AdBuilder().build()
        previous = price_state_of(ad)
        ad.status = AdStatus.REMOVED_BY_USER

        self.assertEqual("removed_by_user", price_observation(ad, previous, _NOW).status)

    def test_an_ad_without_a_price_records_nothing(self):
        ad = AdBuilder().with_price(0).build()

        self.assertIsNone(price_observation(ad, None, _NOW))


if __name__ == "__main__":
    unittest.main()
