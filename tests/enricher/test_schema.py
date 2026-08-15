from __future__ import annotations

import unittest

from data.models import RenovationNeeded
from enricher.results import EvaluationResult, ScreeningResult
from enricher.schema import EVALUATION_SCHEMA, RENOVATION_NEEDED_VALUES, SCORE_FIELD_NAMES, SCREENING_SCHEMA


def _example_evaluation_payload() -> dict:
    return {
        **{name: 6 for name in SCORE_FIELD_NAMES},
        "renovation_needed": "cosmetic",
        "style_tag": "DATED",
        "summary": "Przecietne mieszkanie w bloku z lat dziewiecdziesiatych.",
        "strengths": ["dobra lokalizacja", "niski czynsz"],
        "concerns": ["kuchnia do wymiany"],
        "attributes": [{"key": "kitchen_type", "value": "zamknieta"}],
    }


class TestStructuredOutputSchemas(unittest.TestCase):

    def test_every_property_is_required_in_both_schemas(self):
        for schema in (SCREENING_SCHEMA, EVALUATION_SCHEMA):
            self.assertEqual(sorted(schema["properties"]), sorted(schema["required"]))

    def test_objects_forbid_additional_properties(self):
        for schema in (SCREENING_SCHEMA, EVALUATION_SCHEMA):
            self.assertFalse(schema["additionalProperties"])

    def test_every_score_is_constrained_to_one_to_ten(self):
        for name in SCORE_FIELD_NAMES:
            self.assertEqual(list(range(1, 11)), EVALUATION_SCHEMA["properties"][name]["enum"])

    def test_every_property_carries_a_description(self):
        for schema in (SCREENING_SCHEMA, EVALUATION_SCHEMA):
            for name, definition in schema["properties"].items():
                self.assertTrue(definition.get("description"), name)

    def test_renovation_values_match_the_database_enum(self):
        self.assertEqual(
            sorted(member.value for member in RenovationNeeded),
            sorted(RENOVATION_NEEDED_VALUES),
        )


class TestResultParsing(unittest.TestCase):

    def test_evaluation_payload_parses_into_scores(self):
        result = EvaluationResult.from_payload(_example_evaluation_payload())

        self.assertEqual(6, result.overall_score)
        self.assertEqual(sorted(SCORE_FIELD_NAMES), sorted(result.scores))
        self.assertEqual({"kitchen_type": "zamknieta"}, dict(result.attributes))

    def test_evaluation_payload_without_a_score_is_rejected(self):
        payload = _example_evaluation_payload()
        del payload["layout_score"]

        with self.assertRaises(ValueError):
            EvaluationResult.from_payload(payload)

    def test_screening_payload_without_rejection_reason_yields_none(self):
        result = ScreeningResult.from_payload(
            {"status": "passed", "rejection_reason": "", "extracted_attributes": []}
        )

        self.assertTrue(result.is_passed)
        self.assertIsNone(result.rejection_reason)

    def test_screening_attributes_are_collapsed_into_a_mapping(self):
        result = ScreeningResult.from_payload({
            "status": "passed",
            "rejection_reason": "",
            "extracted_attributes": [
                {"key": "bathroom_count", "value": "2"},
                {"key": "agency_fee", "value": "tak"},
            ],
        })

        self.assertEqual({"bathroom_count": "2", "agency_fee": "tak"}, dict(result.extracted_attributes))


if __name__ == "__main__":
    unittest.main()
