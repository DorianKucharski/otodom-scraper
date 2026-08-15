from __future__ import annotations

import unittest

from enricher.image_source import media_type_of, select_images
from tests.enricher.ad_builder import AdBuilder


def _positions(limit: int, image_count: int) -> list[int]:
    images = AdBuilder().with_images(image_count).build().images
    return [image.position for image in select_images(images, limit)]


class TestSelectImages(unittest.TestCase):

    def test_all_images_are_kept_when_below_the_limit(self):
        self.assertEqual([0, 1, 2], _positions(limit=8, image_count=3))

    def test_selection_spans_the_whole_gallery(self):
        selected = _positions(limit=8, image_count=20)

        self.assertEqual(8, len(selected))
        self.assertEqual(0, selected[0])
        self.assertEqual(19, selected[-1])

    def test_selection_keeps_ascending_order(self):
        selected = _positions(limit=6, image_count=30)

        self.assertEqual(sorted(selected), selected)

    def test_selection_has_no_duplicates(self):
        selected = _positions(limit=8, image_count=9)

        self.assertEqual(len(set(selected)), len(selected))

    def test_a_single_image_is_allowed(self):
        self.assertEqual([0], _positions(limit=1, image_count=10))

    def test_no_images_yields_nothing(self):
        self.assertEqual([], _positions(limit=8, image_count=0))


class TestMediaTypeOf(unittest.TestCase):

    def test_extension_decides_the_media_type(self):
        self.assertEqual("image/png", media_type_of("https://cdn/photo.png"))

    def test_query_string_is_ignored(self):
        self.assertEqual("image/webp", media_type_of("https://cdn/photo.webp?width=800"))

    def test_unknown_extension_falls_back_to_jpeg(self):
        self.assertEqual("image/jpeg", media_type_of("https://cdn/photo"))


if __name__ == "__main__":
    unittest.main()
