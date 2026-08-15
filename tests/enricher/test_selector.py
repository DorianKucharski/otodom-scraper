from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from enricher.selector import AdFilter, evaluation_candidate_query, screening_candidate_query

_ENGINE = create_engine("postgresql+psycopg2://user:pass@localhost/db")


def _compiled(query) -> str:
    return str(query.statement.compile(compile_kwargs={"literal_binds": True}))


def _screening_sql(ad_filter: AdFilter, force: bool = False) -> str:
    with Session(bind=_ENGINE) as session:
        return _compiled(screening_candidate_query(session, ad_filter, prompt_version="abc123", force=force))


def _evaluation_sql(
        ad_filter: AdFilter,
        force: bool = False,
        require_passed_screening: bool = True,
) -> str:
    with Session(bind=_ENGINE) as session:
        return _compiled(evaluation_candidate_query(
            session,
            ad_filter,
            prompt_version="abc123",
            price_drift_threshold=0.05,
            force=force,
            require_passed_screening=require_passed_screening,
        ))


class TestScreeningCandidateQuery(unittest.TestCase):

    def test_only_active_ads_are_screened(self):
        sql = _screening_sql(AdFilter())

        self.assertIn("ads.status = 'active'", sql)

    def test_stale_prompt_version_reselects_the_ad(self):
        sql = _screening_sql(AdFilter())

        self.assertIn("ad_screenings.prompt_version != 'abc123'", sql)

    def test_unchanged_ads_are_detected_by_modification_time(self):
        sql = _screening_sql(AdFilter())

        self.assertIn("ad_screenings.ad_modified_at IS DISTINCT FROM ads.modified_at", sql)

    def test_failed_screenings_stop_being_retried_after_three_attempts(self):
        sql = _screening_sql(AdFilter())

        self.assertIn("ad_screenings.attempts < 3", sql)

    def test_force_drops_the_freshness_conditions(self):
        sql = _screening_sql(AdFilter(), force=True)

        self.assertNotIn("prompt_version", sql)

    def test_city_filter_joins_the_city_table(self):
        sql = _screening_sql(AdFilter(city="Lublin", voivodeship="lubelskie"))

        self.assertIn("JOIN cities", sql)
        self.assertIn("lower(cities.name) LIKE lower('Lublin')", sql)

    def test_city_filter_also_matches_the_normalized_slug(self):
        sql = _screening_sql(AdFilter(city="Kraków", voivodeship="Małopolskie"))

        self.assertIn("cities.code = 'krakow'", sql)
        self.assertIn("provinces.code = 'malopolskie'", sql)

    def test_city_written_without_polish_characters_matches_too(self):
        sql = _screening_sql(AdFilter(city="krakow", voivodeship="malopolskie"))

        self.assertIn("cities.code = 'krakow'", sql)

    def test_district_filter_matches_by_name_or_slug(self):
        sql = _screening_sql(AdFilter(district="Stare Miasto", city="Kraków", voivodeship="Małopolskie"))

        self.assertIn("JOIN districts", sql)
        self.assertIn("districts.code = 'stare-miasto'", sql)

    def test_object_type_filter_keeps_ads_without_a_type(self):
        sql = _screening_sql(AdFilter(object_types=("APARTMENT",)))

        self.assertIn("ads.object_type IN ('APARTMENT')", sql)
        self.assertIn("ads.object_type IS NULL", sql)

    def test_url_filter_ignores_other_filters(self):
        sql = _screening_sql(AdFilter(url="https://otodom.pl/x", city="lublin", voivodeship="lubelskie"))

        self.assertIn("ads.url = 'https://otodom.pl/x'", sql)
        self.assertNotIn("JOIN cities", sql)


class TestEvaluationCandidateQuery(unittest.TestCase):

    def test_only_ads_that_passed_screening_are_evaluated(self):
        sql = _evaluation_sql(AdFilter())

        self.assertIn("JOIN ad_screenings", sql)
        self.assertIn("ad_screenings.status = 'passed'", sql)

    def test_price_drift_beyond_threshold_reselects_the_ad(self):
        sql = _evaluation_sql(AdFilter())

        self.assertIn("abs(ads.price_value - ad_evaluations.price_at_evaluation)", sql)
        self.assertIn("ad_evaluations.price_at_evaluation * 0.05", sql)

    def test_dry_run_does_not_require_a_screening_row(self):
        sql = _evaluation_sql(AdFilter(), require_passed_screening=False)

        self.assertNotIn("JOIN ad_screenings", sql)


if __name__ == "__main__":
    unittest.main()
