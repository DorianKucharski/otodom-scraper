from __future__ import annotations

import unittest

from sqlalchemy.dialects import postgresql

from api.query import build_search_statements, object_type_of, offer_type_of
from api.schemas import AdSearchQuery, FeatureMatchMode, SortDirection, SortField
from data.models import Ad


def _sql(**overrides) -> str:
    statements = build_search_statements(AdSearchQuery(**overrides))
    return str(statements.rows.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    ))


class TestSearchStatement(unittest.TestCase):

    def test_default_query_selects_active_ads_only(self):
        self.assertIn("ads.status IN ('active')", _sql())

    def test_price_range_is_applied(self):
        sql = _sql(min_price=500000, max_price=900000)

        self.assertIn("ads.price_value >= 500000", sql)
        self.assertIn("ads.price_value <= 900000", sql)

    def test_city_filter_matches_case_insensitively(self):
        sql = _sql(cities=["Lublin"])

        self.assertIn("lower(cities.name) IN ('lublin')", sql)

    def test_radius_filter_uses_postgis(self):
        sql = _sql(latitude=51.2465, longitude=22.5684, radius_m=1000)

        self.assertIn("ST_DWithin", sql)
        self.assertIn("ST_MakePoint(22.5684, 51.2465)", sql)

    def test_requiring_all_features_produces_one_exists_per_feature(self):
        sql = _sql(features=["balcony", "lift"], feature_match=FeatureMatchMode.ALL)

        self.assertEqual(2, sql.count("ad_all_features.value IN ("))
        self.assertIn("IN ('balcony', 'balkon')", sql)
        self.assertIn("IN ('lift')", sql)

    def test_requiring_any_feature_produces_a_single_exists(self):
        sql = _sql(features=["balcony", "lift"], feature_match=FeatureMatchMode.ANY)

        self.assertEqual(1, sql.count("ad_all_features.value IN ("))
        self.assertIn("IN ('balcony', 'balkon', 'lift')", sql)

    def test_excluded_features_are_negated(self):
        sql = _sql(excluded_features=["basement"])

        self.assertIn("NOT (EXISTS", sql)

    def test_minimum_features_count_uses_the_union_view(self):
        sql = _sql(min_features_count=10)

        self.assertIn("FROM ad_all_features", sql)
        self.assertIn(">= 10", sql)

    def test_ai_score_minimums_reach_the_evaluation_table(self):
        sql = _sql(min_overall_score=7, min_photo_trust_score=5)

        self.assertIn("ad_evaluations.overall_score >= 7", sql)
        self.assertIn("ad_evaluations.photo_trust_score >= 5", sql)

    def test_attribute_filters_read_the_jsonb_column(self):
        sql = _sql(attributes=["kitchen_type:zamknieta"])

        self.assertIn("ad_evaluations.attributes ->> 'kitchen_type'", sql)
        self.assertIn("'zamknieta'", sql)

    def test_malformed_attribute_filter_is_ignored(self):
        self.assertNotIn("attributes ->>", _sql(attributes=["kitchen_type"]))

    def test_ground_floor_can_be_excluded(self):
        sql = _sql(exclude_ground_floor=True)

        self.assertIn("GROUND_FLOOR", sql)
        self.assertIn("SUBSTRING(ads.flat_floor FROM 7)", sql)

    def test_top_floor_can_be_excluded(self):
        sql = _sql(exclude_top_floor=True)

        self.assertIn("ads.building_number_of_floors", sql)

    def test_sorting_by_an_ai_score_orders_by_the_evaluation_column(self):
        sql = _sql(sort=SortField("overall_score"), direction=SortDirection.DESC)

        self.assertIn("ORDER BY ad_evaluations.overall_score DESC NULLS LAST", sql)

    def test_sorting_by_features_count_orders_by_the_subquery(self):
        sql = _sql(sort=SortField("features_count"))

        self.assertIn("ORDER BY (SELECT count(*)", sql)

    def test_requiring_an_evaluation_filters_out_unevaluated_ads(self):
        self.assertIn("ad_evaluations.ad_id IS NOT NULL", _sql(require_evaluation=True))

    def test_pagination_is_applied(self):
        sql = _sql(limit=25, offset=50)

        self.assertIn("LIMIT 25", sql)
        self.assertIn("OFFSET 50", sql)

    def test_total_statement_counts_the_same_conditions(self):
        statements = build_search_statements(AdSearchQuery(min_price=500000))
        total_sql = str(statements.total.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        ))

        self.assertIn("count(*)", total_sql)
        self.assertIn("ads.price_value >= 500000", total_sql)
        self.assertNotIn("LIMIT", total_sql)


class TestOfferTypeFilter(unittest.TestCase):

    def test_rent_uses_the_stored_offer_type_first(self):
        sql = _sql(offer_types=["RENT"])

        self.assertIn("WHEN (ads.offer_type IS NOT NULL) THEN ads.offer_type", sql)
        self.assertIn("IN ('RENT')", sql)

    def test_an_unknown_offer_type_is_inferred_from_market_and_price(self):
        sql = _sql(offer_types=["SALE"])

        self.assertIn("WHEN (ads.market IN ('PRIMARY', 'SECONDARY')) THEN 'SALE'", sql)
        self.assertIn("WHEN (ads.price_value < 30000) THEN 'RENT'", sql)

    def test_the_python_rule_matches_the_sql_rule(self):
        cases = [
            (Ad(offer_type="RENT", market="PRIMARY", price_value=900000), "RENT"),
            (Ad(offer_type=None, market="SECONDARY", price_value=2500), "SALE"),
            (Ad(offer_type=None, market="ALL", price_value=3200), "RENT"),
            (Ad(offer_type=None, market="", price_value=450000), "SALE"),
        ]
        for ad, expected in cases:
            self.assertEqual(expected, offer_type_of(ad))


class TestObjectTypeFilter(unittest.TestCase):

    def test_the_filter_uses_the_inferred_object_type(self):
        sql = _sql(object_types=["HOUSE"])

        self.assertIn("WHEN (ads.object_type IS NOT NULL) THEN ads.object_type", sql)
        self.assertIn("ads.title ~*", sql)

    def test_the_stored_object_type_wins(self):
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
            self.assertEqual(expected, object_type_of(Ad(title=title)), title)


class TestFeatureSynonyms(unittest.TestCase):

    def test_a_polish_label_matches_the_english_code_too(self):
        self.assertIn("IN ('LIFT', 'winda')", _sql(features=["winda"]))

    def test_an_excluded_feature_excludes_every_synonym(self):
        self.assertIn("IN ('basement', 'piwnica')", _sql(excluded_features=["piwnica"]))

    def test_an_unknown_feature_is_matched_as_is(self):
        self.assertIn("IN ('sauna')", _sql(features=["sauna"]))


class TestTrackingFilters(unittest.TestCase):

    def test_dismissed_ads_are_hidden_by_default(self):
        sql = _sql()

        self.assertIn("ad_tracking.status IS NULL OR (ad_tracking.status NOT IN ('rejected', 'unavailable'))", sql)

    def test_dismissed_ads_can_be_shown(self):
        self.assertNotIn("NOT IN ('rejected', 'unavailable')", _sql(hide_dismissed=False))

    def test_only_ads_with_the_chosen_statuses(self):
        sql = _sql(tracking_statuses=["to_call", "viewing_scheduled"])

        self.assertIn("ad_tracking.status IN ('to_call', 'viewing_scheduled')", sql)

    def test_the_total_joins_the_tracking_table(self):
        statements = build_search_statements(AdSearchQuery(tracking_statuses=["to_call"]))
        total_sql = str(statements.total.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        ))

        self.assertIn("LEFT OUTER JOIN ad_tracking", total_sql)


class TestSortFieldEnum(unittest.TestCase):

    def test_every_ai_score_can_be_used_for_sorting(self):
        from enricher.schema import SCORE_FIELD_NAMES

        for score_name in SCORE_FIELD_NAMES:
            self.assertEqual(score_name, SortField(score_name).value)

    def test_every_ai_score_has_a_minimum_filter(self):
        from enricher.schema import SCORE_FIELD_NAMES

        for score_name in SCORE_FIELD_NAMES:
            self.assertIn(f"min_{score_name}", AdSearchQuery.model_fields)


if __name__ == "__main__":
    unittest.main()
