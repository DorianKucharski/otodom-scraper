from __future__ import annotations

import unittest

from enricher.fingerprint import content_fingerprint, has_price_drifted
from tests.enricher.ad_builder import AdBuilder


class TestContentFingerprint(unittest.TestCase):

    def test_fingerprint_is_stable_for_the_same_content(self):
        first = content_fingerprint(AdBuilder().with_feature("balcony").with_images(3).build())
        second = content_fingerprint(AdBuilder().with_feature("balcony").with_images(3).build())

        self.assertEqual(first, second)

    def test_fingerprint_ignores_price_changes(self):
        original = content_fingerprint(AdBuilder().with_price(750_000, 12_500).build())
        repriced = content_fingerprint(AdBuilder().with_price(690_000, 11_500).build())

        self.assertEqual(original, repriced)

    def test_fingerprint_changes_when_description_changes(self):
        original = content_fingerprint(AdBuilder().with_description("<p>Opis</p>").build())
        rewritten = content_fingerprint(AdBuilder().with_description("<p>Nowy opis</p>").build())

        self.assertNotEqual(original, rewritten)

    def test_fingerprint_changes_when_a_feature_is_added(self):
        original = content_fingerprint(AdBuilder().with_feature("balcony").build())
        extended = content_fingerprint(AdBuilder().with_feature("balcony").with_feature("lift").build())

        self.assertNotEqual(original, extended)

    def test_fingerprint_changes_when_photos_change(self):
        original = content_fingerprint(AdBuilder().with_images(3).build())
        with_more_photos = content_fingerprint(AdBuilder().with_images(4).build())

        self.assertNotEqual(original, with_more_photos)

    def test_fingerprint_ignores_feature_order(self):
        original = content_fingerprint(AdBuilder().with_feature("balcony").with_feature("lift").build())
        reordered = content_fingerprint(AdBuilder().with_feature("lift").with_feature("balcony").build())

        self.assertEqual(original, reordered)


class TestHasPriceDrifted(unittest.TestCase):

    def test_price_change_within_threshold_does_not_drift(self):
        self.assertFalse(has_price_drifted(current_price=760_000, evaluated_price=750_000, threshold=0.05))

    def test_price_change_beyond_threshold_drifts(self):
        self.assertTrue(has_price_drifted(current_price=700_000, evaluated_price=750_000, threshold=0.05))

    def test_unchanged_price_does_not_drift(self):
        self.assertFalse(has_price_drifted(current_price=750_000, evaluated_price=750_000, threshold=0.05))

    def test_missing_evaluated_price_drifts(self):
        self.assertTrue(has_price_drifted(current_price=750_000, evaluated_price=None, threshold=0.05))


if __name__ == "__main__":
    unittest.main()
