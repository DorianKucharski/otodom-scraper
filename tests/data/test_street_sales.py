from __future__ import annotations

import unittest

from data.street_sales import StreetSale, StreetSalesIndex, rcn_street_key


def _sale(price_per_m2: float, latitude: float = 50.1058, area: float = 100.0, key: str = "dozynkowa",
          market: str = "SECONDARY") -> StreetSale:
    return StreetSale(key=key, market=market, latitude=latitude, longitude=19.9433, area=area, price_per_m2=price_per_m2)


class TestStreetSales(unittest.TestCase):

    def test_the_rcn_address_gives_the_street_key(self):
        self.assertEqual("dozynkowa", rcn_street_key("MSC:KRAKÓW;UL:DOŻYNKOWA;NR_PORZ:35C"))
        self.assertIsNone(rcn_street_key("MSC:MODLNICA;NR_PORZ:7"))

    def test_sales_on_the_same_street_give_a_median(self):
        index = StreetSalesIndex([_sale(10_000), _sale(10_500), _sale(11_000), _sale(20_000, key="nowa")])

        stats = index.stats_for("dozynkowa", 50.1058, 19.9433, 107.0, "SECONDARY")

        self.assertEqual(3, stats.count)
        self.assertEqual(10_500, stats.median_price_per_m2)

    def test_the_far_end_of_a_long_street_and_other_sizes_do_not_count(self):
        index = StreetSalesIndex([_sale(10_000), _sale(10_500), _sale(11_000, latitude=50.13), _sale(10_800, area=40.0)])

        self.assertIsNone(index.stats_for("dozynkowa", 50.1058, 19.9433, 107.0, "SECONDARY"))

    def test_other_markets_fill_in_when_the_same_market_is_short(self):
        index = StreetSalesIndex([_sale(10_000), _sale(12_000, market="PRIMARY"), _sale(12_500, market="PRIMARY")])

        self.assertEqual(12_000, index.stats_for("dozynkowa", 50.1058, 19.9433, 100.0, "SECONDARY").median_price_per_m2)

    def test_a_listing_without_a_street_gets_nothing(self):
        self.assertIsNone(StreetSalesIndex([_sale(10_000)] * 3).stats_for(None, 50.1, 19.9, 100.0, None))


if __name__ == "__main__":
    unittest.main()
