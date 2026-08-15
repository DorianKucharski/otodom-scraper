from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from data.ad_dto import AdDto, PriceDto
from data.models import AdStatus
from tests.enricher.ad_builder import AdBuilder

_SOURCE_MODIFIED_AT = datetime(2026, 7, 1, 12, 0)


def _dto(price: int = 750_000, modified_at: datetime = _SOURCE_MODIFIED_AT) -> AdDto:
    return AdDto(
        id=1,
        public_id="ABC123",
        slug="mieszkanie",
        url="https://www.otodom.pl/pl/oferta/test",
        title="Mieszkanie 3 pokoje",
        description="<p>Opis</p>",
        created_at=datetime(2026, 6, 1),
        modified_at=modified_at,
        status="active",
        market="SECONDARY",
        advertiser_type="private",
        price=PriceDto(value=price, currency="PLN", per_m2=price // 60),
        location=None,
        property=None,
        owner=None,
        features=[],
        images=[],
        characteristics=[],
    )


class TestAdUpdate(unittest.TestCase):

    def test_update_stores_the_source_modification_time(self):
        ad = AdBuilder().build()

        ad.update(_dto())

        self.assertEqual(_SOURCE_MODIFIED_AT, ad.modified_at)

    def test_update_stamps_when_we_last_checked(self):
        ad = AdBuilder().build()
        before = datetime.now()

        ad.update(_dto())

        self.assertGreaterEqual(ad.scraped_at, before)

    def test_an_unchanged_ad_keeps_the_same_modification_time(self):
        ad = AdBuilder().build()

        ad.update(_dto())
        first = ad.modified_at
        ad.update(_dto())

        self.assertEqual(first, ad.modified_at)

    def test_a_changed_ad_gets_the_new_modification_time(self):
        ad = AdBuilder().build()
        ad.update(_dto())

        ad.update(_dto(price=690_000, modified_at=_SOURCE_MODIFIED_AT + timedelta(days=3)))

        self.assertEqual(_SOURCE_MODIFIED_AT + timedelta(days=3), ad.modified_at)
        self.assertEqual(690_000, ad.price_value)

    def test_outdating_does_not_touch_the_source_modification_time(self):
        ad = AdBuilder().build()
        ad.update(_dto())

        ad.outdate()

        self.assertEqual(AdStatus.OUTDATED, ad.status)
        self.assertEqual(_SOURCE_MODIFIED_AT, ad.modified_at)


class TestShouldUpdate(unittest.TestCase):

    def test_a_recently_checked_ad_is_not_rechecked(self):
        ad = AdBuilder().build()
        ad.scraped_at = datetime.now() - timedelta(days=2)

        self.assertFalse(ad.should_update(update_if_older_than_days=30))

    def test_a_long_unchecked_ad_is_rechecked(self):
        ad = AdBuilder().build()
        ad.scraped_at = datetime.now() - timedelta(days=45)

        self.assertTrue(ad.should_update(update_if_older_than_days=30))

    def test_a_stale_source_timestamp_alone_does_not_trigger_a_recheck(self):
        ad = AdBuilder().build()
        ad.modified_at = datetime.now() - timedelta(days=400)
        ad.scraped_at = datetime.now()

        self.assertFalse(ad.should_update(update_if_older_than_days=30))

    def test_zero_days_always_rechecks(self):
        ad = AdBuilder().build()
        ad.scraped_at = datetime.now()

        self.assertTrue(ad.should_update(update_if_older_than_days=0))


if __name__ == "__main__":
    unittest.main()
