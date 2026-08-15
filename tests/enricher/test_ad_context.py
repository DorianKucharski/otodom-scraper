from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
