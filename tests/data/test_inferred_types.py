from __future__ import annotations

import unittest

from data.inferred_types import inferred_types_view_sql, object_type_of, offer_type_of
from data.models import Ad


class TestOfferType(unittest.TestCase):

    def test_the_stored_offer_type_wins(self):
        self.assertEqual("RENT", offer_type_of(Ad(offer_type="RENT", market="PRIMARY", price_value=900000)))

    def test_primary_or_secondary_market_means_sale(self):
        self.assertEqual("SALE", offer_type_of(Ad(market="SECONDARY", price_value=2500)))

    def test_a_low_price_without_a_market_means_rent(self):
        self.assertEqual("RENT", offer_type_of(Ad(market="ALL", price_value=3200)))

    def test_a_high_price_without_a_market_means_sale(self):
        self.assertEqual("SALE", offer_type_of(Ad(market="", price_value=450000)))


class TestObjectType(unittest.TestCase):

    def test_an_investment_url_wins_over_the_stored_type(self):
        ad = Ad(url="https://www.otodom.pl/pl/inwestycja/stawowa-residence-ID4ui2Y", object_type="APARTMENT")

        self.assertEqual("INVESTMENT", object_type_of(ad))

    def test_the_stored_object_type_wins_otherwise(self):
        self.assertEqual("HOUSE", object_type_of(Ad(object_type="HOUSE", flat_floor="FLOOR_2", title="Mieszkanie")))

    def test_a_floor_means_a_flat(self):
        self.assertEqual("APARTMENT", object_type_of(Ad(flat_floor="GROUND_FLOOR", title="Dom")))

    def test_a_detached_building_means_a_house(self):
        self.assertEqual("HOUSE", object_type_of(Ad(building_type="SEMI_DETACHED", title="Okazja")))

    def test_a_poorly_parsed_ad_falls_back_to_its_title(self):
        cases = [
            ("Dom z dużą działką 2500 m²", "HOUSE"),
            ("DOMEK W LESIE", "HOUSE"),
            ("Segment środkowy 124m2 z tarasem", "HOUSE"),
            ("Nowe osiedle - zabudowa szeregowa", "HOUSE"),
            ("Kawalerka Grochów", "APARTMENT"),
            ("Wynajmę przestronny apartament 4 pokoje", "APARTMENT"),
            ("Domofon, winda, 3-pok. z balkonem", "APARTMENT"),
            ("Super okazja !!!", None),
        ]
        for title, expected in cases:
            self.assertEqual(expected, object_type_of(Ad(url="https://www.otodom.pl/pl/oferta/x", title=title)), title)


class TestInferredTypesView(unittest.TestCase):

    def test_the_view_sql_carries_every_rule(self):
        sql = inferred_types_view_sql()

        self.assertIn("CREATE MATERIALIZED VIEW IF NOT EXISTS ad_inferred_types", sql)
        self.assertIn("strpos(ads.url, '/inwestycja/') > 0", sql)
        self.assertIn("ads.title ~*", sql)
        self.assertIn("ads.market IN ('PRIMARY', 'SECONDARY')", sql)

    def test_the_view_sql_has_no_placeholders_or_percent_signs(self):
        sql = inferred_types_view_sql()

        self.assertNotIn("%", sql)
        self.assertNotIn(":", sql)


if __name__ == "__main__":
    unittest.main()
