import json
from datetime import datetime
import unittest

from sqlalchemy.dialects import postgresql

from api.assistant.interpret import interpretation_schema, plan_from_payload
from api.assistant.rank import Candidate, ad_card, ranked_from_payload, ranking_schema
from api.query import build_search_statements, keyword_relevance
from api.schemas import AdSearchQuery, FacetValue, FacetsResponse, RangeFacet
from data.models import AdEvaluation, AdMarketSignals, AdScreening
from tests.enricher.ad_builder import AdBuilder


def _facets() -> FacetsResponse:
    def values(*names):
        return [FacetValue(value=name, label=name, count=1) for name in names]

    empty = RangeFacet(min=None, max=None)
    return FacetsResponse(
        offer_types=[], object_types=[], voivodeships=values("małopolskie"), cities=values("Kraków", "Łódź"),
        districts=values("Podgórze", "Dębniki"), features=values("balkon", "winda"), building_types=[],
        building_materials=[], building_heating=[], markets=[], advertiser_types=[], property_conditions=[],
        style_tags=[], renovation_needed=[], price=empty, price_per_m2=empty, area=empty, rooms=empty,
        building_year=empty,
    )


def _payload(**overrides) -> dict:
    payload = {
        "understood": "Dwa pokoje w Krakowie do 900 tys.",
        "offer_types": ["SALE"], "object_types": ["APARTMENT"], "markets": [], "advertiser_types": [],
        "building_types": [], "building_materials": [], "building_heating": [], "property_conditions": [],
        "voivodeships": [], "cities": ["krakow"], "districts": ["Podgorze", "Kazimierz"], "near": [],
        "limits": [{"field": "max_price", "value": 900000.4}, {"field": "min_area", "value": 45.5}],
        "exclude_ground_floor": True, "exclude_top_floor": False,
        "features": ["winda", "basen"], "excluded_features": [],
        "keywords": ["słoneczn", "Słoneczn", "zieleń"],
        "criteria": [{"text": "jasne mieszkanie", "importance": "must"}, {"text": " ", "importance": "nice"}],
        "sort": "relevance", "direction": "desc",
    }
    payload.update(overrides)
    return payload


class TestInterpretationSchema(unittest.TestCase):

    def test_the_schema_has_no_optional_or_union_parameters(self):
        schema_text = json.dumps(interpretation_schema(_facets()))

        self.assertNotIn('"null"', schema_text)
        self.assertNotIn("anyOf", schema_text)
        self.assertEqual(set(interpretation_schema(_facets())["properties"]), set(interpretation_schema(_facets())["required"]))

    def test_features_are_limited_to_known_labels(self):
        features = interpretation_schema(_facets())["properties"]["features"]

        self.assertEqual(["balkon", "winda"], features["items"]["enum"])


class TestPlanFromPayload(unittest.TestCase):

    def test_names_resolve_to_stored_spelling_and_unknown_ones_warn(self):
        plan = plan_from_payload(_payload(), _facets())

        self.assertEqual(["Kraków"], plan.query.cities)
        self.assertEqual(["Podgórze"], plan.query.districts)
        self.assertTrue(any("Kazimierz" in warning for warning in plan.warnings))

    def test_limits_become_query_fields(self):
        query = plan_from_payload(_payload(), _facets()).query

        self.assertEqual((900000, 45.5, True), (query.max_price, query.min_area, query.exclude_ground_floor))

    def test_unknown_features_are_dropped_and_keywords_deduplicated(self):
        plan = plan_from_payload(_payload(), _facets())

        self.assertEqual(["winda"], plan.query.features)
        self.assertEqual(("słoneczn", "zieleń"), plan.keywords)
        self.assertEqual(1, len(plan.criteria))

    def test_a_place_outside_poland_is_ignored(self):
        near = [{"place": "Paryż", "latitude": 48.85, "longitude": 2.35, "radius_m": 1000}]

        plan = plan_from_payload(_payload(near=near), _facets())

        self.assertIsNone(plan.query.latitude)
        self.assertTrue(any("Paryż" in warning for warning in plan.warnings))

    def test_a_place_in_poland_sets_a_clamped_radius(self):
        near = [{"place": "Kazimierz", "latitude": 50.05, "longitude": 19.94, "radius_m": 10}]

        query = plan_from_payload(_payload(near=near), _facets()).query

        self.assertEqual((50.05, 19.94, 300), (query.latitude, query.longitude, query.radius_m))

    def test_a_wide_radius_searches_the_surroundings_instead_of_the_city(self):
        near = [{"place": "Warszawa", "latitude": 52.23, "longitude": 21.01, "radius_m": 30000}]

        plan = plan_from_payload(_payload(near=near), _facets())

        self.assertEqual(([], [], 30000), (plan.query.cities, plan.query.districts, plan.query.radius_m))

    def test_an_explicit_sort_is_kept(self):
        plan = plan_from_payload(_payload(sort="price_value", direction="asc"), _facets())

        self.assertEqual(("price_value", "asc", "price_value"), (plan.query.sort.value, plan.query.direction.value, plan.sort))


class TestKeywordRelevance(unittest.TestCase):

    def test_keywords_order_candidates_without_filtering_them(self):
        statements = build_search_statements(
            AdSearchQuery(), relevance=keyword_relevance(["50%_x"]), relevance_first=True
        )
        sql = str(statements.page.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

        self.assertIn("ORDER BY CASE WHEN", sql)
        self.assertIn("'%%50!%%!_x%%' ESCAPE '!'", sql)
        self.assertNotIn("WHERE ads.title ILIKE", sql)

    def test_no_keywords_means_no_relevance(self):
        self.assertIsNone(keyword_relevance([]))


class TestRanking(unittest.TestCase):

    def _candidate(self, ad_id: int) -> Candidate:
        ad = AdBuilder().with_id(ad_id).with_location().build()
        return Candidate(summary=None, card=ad_card(ad, None, None, 500), evaluated=False)

    def test_the_schema_only_allows_candidate_ids(self):
        schema = ranking_schema([3, 5])

        self.assertEqual([3, 5], schema["properties"]["results"]["items"]["properties"]["ad_id"]["enum"])

    def test_results_are_deduplicated_and_sorted_by_fit(self):
        candidates = (self._candidate(3), self._candidate(5))
        payload = {"results": [
            {"ad_id": 3, "fit_score": 6, "headline": "a", "matches": [], "gaps": []},
            {"ad_id": 5, "fit_score": 9, "headline": "b", "matches": ["x"], "gaps": [""]},
            {"ad_id": 3, "fit_score": 10, "headline": "c", "matches": [], "gaps": []},
            {"ad_id": 99, "fit_score": 10, "headline": "d", "matches": [], "gaps": []},
        ]}

        ranked = ranked_from_payload(payload, candidates)

        self.assertEqual([(5, 9), (3, 6)], [(item.candidate.card.id, item.fit_score) for item in ranked])
        self.assertEqual((), ranked[0].gaps)

    def test_a_card_carries_the_evaluation_and_screening_facts(self):
        ad = AdBuilder().with_location().build()
        evaluation = AdEvaluation(
            overall_score=8, finish_quality_score=7, freshness_score=7, move_in_readiness_score=9, layout_score=6,
            natural_light_score=9, building_condition_score=6, location_score=8, value_for_money_score=5,
            photo_trust_score=8, renovation_needed="none", summary="Jasne.", strengths=["światło"], concerns=[],
            attributes={"kitchen_type": "otwarta"},
        )

        card = ad_card(ad, evaluation, AdScreening(extracted_attributes={"orientation": "południe"}), 500)

        self.assertIn("światło 9", card.evaluation)
        self.assertIn("kitchen_type: otwarta", card.evaluation)
        self.assertEqual("orientation: południe", card.screening_attributes)
        self.assertEqual("2 z 4", card.floor)

    def test_a_card_carries_the_market_history_and_warnings(self):
        ad = AdBuilder().with_price(1_099_000).build()
        signals = AdMarketSignals(
            listings_count=5, active_listings_count=1, advertisers_count=1, first_listed_at=datetime(2026, 4, 27),
            days_on_market=180, first_price=1_099_000, comparables_median_price_per_m2=11_766, comparables_count=34,
            comparables_radius_m=1500, price_vs_comparables_pct=-22.2, transactions_median_price_per_m2=11_502,
            transactions_count=10, transactions_radius_m=1500, price_vs_transactions_pct=-20.4,
            location_notes=["Pinezka jest 834 m od granicy miasta Kraków."], area_notes=[], previous_sale_price=None,
        )

        card = ad_card(ad, None, None, 500, signals)

        self.assertIn("180 dni na rynku", card.market_history)
        self.assertIn("5 ogłoszeń", card.market_history)
        self.assertIn("prawdziwych transakcji", card.market_history)
        self.assertIn("834 m od granicy", card.market_history)

    def test_a_card_without_signals_has_no_market_history(self):
        self.assertIsNone(ad_card(AdBuilder().build(), None, None, 500).market_history)


if __name__ == "__main__":
    unittest.main()
