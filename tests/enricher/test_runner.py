from __future__ import annotations

import unittest
from datetime import datetime

from data.models import AdEvaluation, AdScreening, EvaluationStatus, ScreeningStatus
from enricher.llm.client import LlmResponse
from enricher.results import EvaluationResult, ScreeningResult
from enricher.runner import AdOutcome, FAILED, PreparedAd, SKIPPED, _evaluation_row, _is_up_to_date, _screening_row, \
    _summarize
from enricher.schema import SCORE_FIELD_NAMES
from tests.enricher.ad_builder import AdBuilder

_FINGERPRINT = "a" * 64
_PROMPT_VERSION = "abc123def456"


def _prepared_ad() -> PreparedAd:
    ad = AdBuilder().with_location().build()
    return PreparedAd(
        ad_id=ad.id,
        ad_modified_at=ad.modified_at,
        price_value=ad.price_value,
        fingerprint=_FINGERPRINT,
        context=None,
        images=(),
    )


def _response(model: str = "claude-sonnet-5") -> LlmResponse:
    return LlmResponse(
        payload={},
        model=model,
        input_tokens=12_000,
        output_tokens=600,
        cache_read_tokens=1_500,
        cache_write_tokens=0,
    )


def _evaluation_result() -> EvaluationResult:
    return EvaluationResult.from_payload({
        **{name: 6 for name in SCORE_FIELD_NAMES},
        "overall_score": 8,
        "renovation_needed": "cosmetic",
        "style_tag": "MODERN",
        "summary": "Zadbane mieszkanie w dobrej lokalizacji.",
        "strengths": ["jasne wnętrze"],
        "concerns": ["kuchnia do wymiany"],
        "attributes": [{"key": "kitchen_type", "value": "otwarta"}],
    })


class TestUpToDateDecision(unittest.TestCase):

    def __screening(self, **overrides) -> AdScreening:
        defaults = {
            "content_fingerprint": _FINGERPRINT,
            "prompt_version": _PROMPT_VERSION,
            "status": ScreeningStatus.PASSED,
        }
        return AdScreening(**{**defaults, **overrides})

    def test_matching_fingerprint_and_prompt_is_up_to_date(self):
        self.assertTrue(_is_up_to_date(self.__screening(), _FINGERPRINT, _PROMPT_VERSION, force=False))

    def test_missing_row_is_not_up_to_date(self):
        self.assertFalse(_is_up_to_date(None, _FINGERPRINT, _PROMPT_VERSION, force=False))

    def test_changed_content_is_not_up_to_date(self):
        self.assertFalse(_is_up_to_date(self.__screening(), "b" * 64, _PROMPT_VERSION, force=False))

    def test_changed_prompt_is_not_up_to_date(self):
        self.assertFalse(_is_up_to_date(self.__screening(), _FINGERPRINT, "other-version", force=False))

    def test_failed_row_is_not_up_to_date(self):
        failed = self.__screening(status=ScreeningStatus.FAILED)

        self.assertFalse(_is_up_to_date(failed, _FINGERPRINT, _PROMPT_VERSION, force=False))

    def test_force_overrides_a_current_row(self):
        self.assertFalse(_is_up_to_date(self.__screening(), _FINGERPRINT, _PROMPT_VERSION, force=True))


class TestScreeningRow(unittest.TestCase):

    def test_row_carries_the_result_and_the_freshness_keys(self):
        result = ScreeningResult.from_payload({
            "status": "rejected",
            "rejection_reason": "Ogłoszenie dotyczy całej inwestycji.",
            "extracted_attributes": [{"key": "bathroom_count", "value": "2"}],
        })

        row = _screening_row(_prepared_ad(), result, _response("claude-haiku-4-5"), _PROMPT_VERSION, "anthropic")

        self.assertEqual(ScreeningStatus.REJECTED, row.status)
        self.assertEqual("Ogłoszenie dotyczy całej inwestycji.", row.rejection_reason)
        self.assertEqual({"bathroom_count": "2"}, row.extracted_attributes)
        self.assertEqual(_FINGERPRINT, row.content_fingerprint)
        self.assertEqual(datetime(2026, 8, 10), row.ad_modified_at)
        self.assertEqual(1, row.attempts)
        self.assertIsNone(row.error_message)

    def test_cost_is_priced_from_the_response_model(self):
        result = ScreeningResult.from_payload({"status": "passed", "rejection_reason": "", "extracted_attributes": []})

        row = _screening_row(_prepared_ad(), result, _response("claude-haiku-4-5"), _PROMPT_VERSION, "anthropic")

        self.assertAlmostEqual(12_000 / 1e6 + 1_500 / 1e6 * 0.1 + 600 / 1e6 * 5, row.cost_usd, places=6)

    def test_unknown_model_leaves_the_cost_empty(self):
        result = ScreeningResult.from_payload({"status": "passed", "rejection_reason": "", "extracted_attributes": []})

        row = _screening_row(_prepared_ad(), result, _response("some-local-model"), _PROMPT_VERSION, "openai")

        self.assertIsNone(row.cost_usd)


class TestEvaluationRow(unittest.TestCase):

    def test_every_score_reaches_its_own_column(self):
        row = _evaluation_row(
            _prepared_ad(), _evaluation_result(), _response(), _PROMPT_VERSION, "anthropic", EvaluationStatus.OK
        )

        self.assertEqual(8, row.overall_score)
        for score_name in SCORE_FIELD_NAMES:
            self.assertIsNotNone(getattr(row, score_name), score_name)

    def test_price_is_snapshotted_for_drift_detection(self):
        row = _evaluation_row(
            _prepared_ad(), _evaluation_result(), _response(), _PROMPT_VERSION, "anthropic", EvaluationStatus.OK
        )

        self.assertEqual(750_000, row.price_at_evaluation)

    def test_lists_and_attributes_become_plain_json_types(self):
        row = _evaluation_row(
            _prepared_ad(), _evaluation_result(), _response(), _PROMPT_VERSION, "anthropic", EvaluationStatus.OK
        )

        self.assertEqual(["jasne wnętrze"], row.strengths)
        self.assertEqual(["kuchnia do wymiany"], row.concerns)
        self.assertEqual({"kitchen_type": "otwarta"}, row.attributes)
        self.assertIsInstance(row.attributes, dict)

    def test_ads_without_photos_are_marked(self):
        row = _evaluation_row(
            _prepared_ad(), _evaluation_result(), _response(), _PROMPT_VERSION, "anthropic", EvaluationStatus.NO_IMAGES
        )

        self.assertEqual(EvaluationStatus.NO_IMAGES, row.status)
        self.assertEqual(0, row.images_evaluated)

    def test_evaluation_row_is_accepted_by_the_orm_mapper(self):
        row = _evaluation_row(
            _prepared_ad(), _evaluation_result(), _response(), _PROMPT_VERSION, "anthropic", EvaluationStatus.OK
        )

        mapped_columns = {column.key for column in AdEvaluation.__table__.columns}
        self.assertTrue(set(SCORE_FIELD_NAMES).issubset(mapped_columns))
        self.assertEqual(row.ad_id, 1)


class TestSummary(unittest.TestCase):

    def test_outcomes_are_folded_into_totals(self):
        outcomes = (
            AdOutcome(ad_id=1, status="passed", input_tokens=1000, output_tokens=100, cost_usd=0.01),
            AdOutcome(ad_id=2, status=SKIPPED),
            AdOutcome(ad_id=3, status=FAILED, error="boom"),
            AdOutcome(ad_id=4, status="rejected", input_tokens=500, output_tokens=50, cost_usd=0.005),
        )

        summary = _summarize("screening", candidates=4, outcomes=outcomes)

        self.assertEqual(2, summary.processed)
        self.assertEqual(1, summary.skipped)
        self.assertEqual(1, summary.failed)
        self.assertEqual(1500, summary.input_tokens)
        self.assertEqual(150, summary.output_tokens)
        self.assertAlmostEqual(0.015, summary.cost_usd)

    def test_an_empty_run_summarises_to_zero(self):
        summary = _summarize("evaluation", candidates=0, outcomes=())

        self.assertEqual(0, summary.processed)
        self.assertEqual(0.0, summary.cost_usd)


if __name__ == "__main__":
    unittest.main()
