from __future__ import annotations

import unittest

from sqlalchemy.dialects import postgresql

from api.query import build_search_statements
from api.schemas import AdSearchQuery, FeatureMatchMode, SortDirection, SortField


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
        self.assertIn("IN ('balcony')", sql)
        self.assertIn("IN ('lift')", sql)

    def test_requiring_any_feature_produces_a_single_exists(self):
        sql = _sql(features=["balcony", "lift"], feature_match=FeatureMatchMode.ANY)

        self.assertEqual(1, sql.count("ad_all_features.value IN ("))
        self.assertIn("IN ('balcony', 'lift')", sql)

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
