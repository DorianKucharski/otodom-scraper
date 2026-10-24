from __future__ import annotations

import unittest

from datetime import datetime

from data.models import AdMarketSignals
from enricher.ad_context import build_ad_context
from enricher.market_context import DistrictPriceStats, MarketContext
from tests.enricher.ad_builder import AdBuilder


class TestAdContext(unittest.TestCase):

    def test_inline_markup_does_not_split_a_sentence(self):
        ad = AdBuilder().with_description("<p>Ładne <b>mieszkanie</b> w centrum</p>").build()

        context = build_ad_context(ad)

        self.assertEqual("Ładne mieszkanie w centrum", context.description)

    def test_list_items_become_separate_lines(self):
        ad = AdBuilder().with_description("<ul><li>2 łazienki</li><li>kuchnia zamknięta</li></ul>").build()

        context = build_ad_context(ad)

        self.assertEqual("2 łazienki\nkuchnia zamknięta", context.description)

    def test_line_breaks_are_preserved(self):
        ad = AdBuilder().with_description("pierwsza<br/>druga").build()

        context = build_ad_context(ad)

        self.assertEqual("pierwsza\ndruga", context.description)

    def test_empty_description_becomes_none(self):
        ad = AdBuilder().with_description("<p></p>").build()

        context = build_ad_context(ad)

        self.assertIsNone(context.description)

    def test_address_lists_known_parts_only(self):
        ad = AdBuilder().with_location().build()

        context = build_ad_context(ad)

        self.assertEqual("Rynek, Stare Miasto, Lublin, lubelskie", context.address)

    def test_price_is_formatted_with_thousand_separators(self):
        ad = AdBuilder().with_price(750_000, 12_500).build()

        context = build_ad_context(ad)

        self.assertEqual("750 000 PLN", context.price_label)
        self.assertEqual("12 500 PLN za metr", context.price_per_m2_label)

    def test_all_feature_groups_are_listed_even_when_empty(self):
        ad = AdBuilder().with_feature("balcony").with_equipment("dishwasher").build()

        context = build_ad_context(ad)

        labels = [label for label, _ in context.feature_groups]
        self.assertIn("Cechy", labels)
        self.assertIn("Zabezpieczenia", labels)
        self.assertEqual(("balcony",), dict(context.feature_groups)["Cechy"])


class TestMarketStatsView(unittest.TestCase):

    def __market_context(self, median: int, p25: int, p75: int) -> MarketContext:
        stats = DistrictPriceStats(
            ad_count=42,
            median_price_per_m2=median,
            p25_price_per_m2=p25,
            p75_price_per_m2=p75,
            is_city_level=False,
        )
        return MarketContext(_stats_by_key={(1, 2, False, None, None): stats})

    def test_expensive_ad_is_placed_in_the_top_quarter(self):
        ad = AdBuilder().with_location().with_price(900_000, 15_000).build()

        context = build_ad_context(ad, market_context=self.__market_context(12_000, 10_000, 14_000))

        self.assertIn("najdroższej ćwiartce", context.market_stats.position_label)
        self.assertIn("25% powyżej mediany", context.market_stats.position_label)

    def test_cheap_ad_is_placed_in_the_bottom_quarter(self):
        ad = AdBuilder().with_location().with_price(500_000, 9_000).build()

        context = build_ad_context(ad, market_context=self.__market_context(12_000, 10_000, 14_000))

        self.assertIn("najtańszej ćwiartce", context.market_stats.position_label)
        self.assertIn("poniżej mediany", context.market_stats.position_label)

    def test_missing_district_stats_leave_the_view_empty(self):
        ad = AdBuilder().with_price(500_000, 9_000).build()

        context = build_ad_context(ad, market_context=MarketContext(_stats_by_key={}))

        self.assertIsNone(context.market_stats)


def _signals(**overrides) -> AdMarketSignals:
    values = dict(
        ad_id=1,
        listing_group_id=1,
        listings_count=5,
        advertisers_count=2,
        first_listed_at=datetime(2025, 12, 2),
        days_on_market=326,
        first_price=1_029_000,
        lowest_price=1_029_000,
        highest_price=1_099_000,
        price_change_pct=6.8,
        comparables_count=24,
        comparables_radius_m=1500,
        comparables_median_price_per_m2=11_400,
        comparables_p25_price_per_m2=10_500,
        comparables_p75_price_per_m2=12_500,
        price_vs_comparables_pct=-19.7,
        location_flags=["near_city_border"],
        location_notes=["Pinezka jest 835 m od granicy miasta Kraków."],
        area_flags=["usable_area_smaller"],
        area_notes=["Opis podaje 96,73 m² powierzchni użytkowej, a ogłoszenie 120 m²."],
        computed_at=datetime(2026, 10, 24),
    )
    values.update(overrides)
    return AdMarketSignals(**values)


class TestMarketSignalsInContext(unittest.TestCase):

    def test_the_listing_history_follows_the_creation_date(self):
        ad = AdBuilder().with_price(1_099_000, 9_158).build()

        context = build_ad_context(ad, signals=_signals())

        self.assertIn("ogłaszany od 2025-12-02", context.created_at_label)
        self.assertIn("326 dni", context.created_at_label)
        self.assertIn("5 ogłoszeń od 2 ogłoszeniodawców", context.created_at_label)
        self.assertIn("1 029 000 zł", context.created_at_label)

    def test_a_fresh_single_listing_keeps_the_plain_date(self):
        ad = AdBuilder().build()

        context = build_ad_context(ad, signals=_signals(listings_count=1, days_on_market=5))

        self.assertEqual("2026-08-01", context.created_at_label)

    def test_location_warnings_follow_the_address(self):
        ad = AdBuilder().with_location().build()

        context = build_ad_context(ad, signals=_signals())

        self.assertIn("835 m od granicy", context.address)

    def test_area_warnings_follow_the_area(self):
        ad = AdBuilder().build()

        context = build_ad_context(ad, signals=_signals())

        self.assertIn("96,73 m² powierzchni użytkowej", context.area_label)

    def test_comparables_stand_in_when_district_stats_are_missing(self):
        ad = AdBuilder().with_price(1_099_000, 9_158).build()

        context = build_ad_context(ad, market_context=MarketContext(_stats_by_key={}), signals=_signals())

        self.assertEqual(11_400, context.market_stats.median_price_per_m2)
        self.assertIn("20% poniżej", context.market_stats.position_label)


if __name__ == "__main__":
    unittest.main()
