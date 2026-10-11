from __future__ import annotations

import unittest

from api.labels import (
    _FEATURE_SYNONYMS, BUILDING_MATERIALS, FEATURE_LABEL_BY_VALUE, STYLE_TAGS, display_label, feature_label, feature_values_for, label_of,
)
from enricher.schema import STYLE_TAG_VALUES


class TestLabels(unittest.TestCase):

    def test_a_known_value_gets_a_polish_label_and_an_explanation(self):
        label = label_of(BUILDING_MATERIALS, "CONCRETE_PLATE")

        self.assertEqual("Wielka płyta", label.label)
        self.assertIn("prefabrykowane", label.description.lower())

    def test_an_unknown_value_is_humanized(self):
        self.assertEqual("Glass blocks", display_label(BUILDING_MATERIALS, "GLASS_BLOCKS"))

    def test_a_missing_value_stays_missing(self):
        self.assertIsNone(display_label(BUILDING_MATERIALS, None))

    def test_every_style_the_enricher_can_return_is_translated(self):
        for value in STYLE_TAG_VALUES:
            self.assertIn(value, STYLE_TAGS)


class TestFeatureLabels(unittest.TestCase):

    def test_english_and_polish_spellings_share_one_label(self):
        self.assertEqual(feature_label("balcony"), feature_label("balkon"))

    def test_the_same_word_for_windows_and_fences_stays_apart(self):
        self.assertNotEqual(feature_label("WOODEN"), feature_label("drewniane"))

    def test_selecting_by_label_or_by_raw_value_matches_the_same_set(self):
        self.assertEqual(feature_values_for("piwnica"), feature_values_for("basement"))

    def test_no_raw_value_belongs_to_two_labels(self):
        raw_values = [raw for raws in _FEATURE_SYNONYMS.values() for raw in raws]

        self.assertEqual(len(raw_values), len(FEATURE_LABEL_BY_VALUE))


if __name__ == "__main__":
    unittest.main()
