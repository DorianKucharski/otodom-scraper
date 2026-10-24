from __future__ import annotations

import unittest

from data.area_checks import APPURTENANT_INCLUDED, ATTIC_SLOPES, USABLE_AREA_SMALLER, area_verdict


class TestAreaVerdict(unittest.TestCase):

    def test_a_smaller_usable_area_in_the_description_is_flagged(self):
        verdict = area_verdict(180.0, "Dom", "Powierzchnia całkowita domu: 180 mkw Powierzchnia użytkowa: ok. 96 mkw.")

        self.assertEqual([USABLE_AREA_SMALLER], verdict.flags)
        self.assertIn("96 m²", verdict.notes[0])
        self.assertIn("88%", verdict.notes[0])

    def test_the_usable_area_can_come_before_the_word(self):
        verdict = area_verdict(110.0, "Mieszkanie", "Mieszkanie 110 m² (96,73 m² powierzchni użytkowej), 4 pokoje.")

        self.assertEqual([USABLE_AREA_SMALLER], verdict.flags)
        self.assertIn("96,73 m²", verdict.notes[0])

    def test_the_usable_area_from_the_land_register_is_found_further_away(self):
        verdict = area_verdict(79.61, "Mieszkanie", "Powierzchnia użytkowa mieszkania jaka widnieje w księdze "
                                                                  "wieczystej to 53,39m2 natomiast po podłodze 62,48m2.")

        self.assertIn(USABLE_AREA_SMALLER, verdict.flags)
        self.assertIn("53,39 m²", verdict.notes[0])

    def test_a_deed_mentioned_in_another_sentence_does_not_count(self):
        verdict = area_verdict(80.0, "Mieszkanie", "Powierzchnia użytkowa zgodna. Księga wieczysta założona, piwnica 6 m2.")

        self.assertNotIn(USABLE_AREA_SMALLER, verdict.flags)

    def test_the_usable_area_of_one_level_is_not_the_whole_flat(self):
        verdict = area_verdict(60.22, "Mieszkanie", "Poziom dolny (powierzchnia użytkowa 28,86 m²): salon z aneksem.")

        self.assertEqual([], verdict.flags)

    def test_the_usable_area_of_an_attic_for_sale_is_not_the_flat(self):
        verdict = area_verdict(45.0, "Mieszkanie", "Można wykupić strych o powierzchni użytkowej około 25 m2.")

        self.assertEqual([], verdict.flags)

    def test_floor_area_against_usable_area_is_flagged(self):
        verdict = area_verdict(73.0, "3 pokoje", "Powierzchnia podłogi: około 73m2 Powierzchnia użytkowa: 37,82m2")

        self.assertIn(USABLE_AREA_SMALLER, verdict.flags)

    def test_a_matching_usable_area_is_fine(self):
        verdict = area_verdict(72.0, "Mieszkanie", "Powierzchnia użytkowa 71,5 m².")

        self.assertEqual([], verdict.flags)

    def test_slopes_are_quoted(self):
        verdict = area_verdict(120.0, "Dwa poziomy", "Na poddaszu sypialnia ze skosami i łazienka.")

        self.assertEqual([ATTIC_SLOPES], verdict.flags)
        self.assertIn("skosami", verdict.notes[0])

    def test_rooms_counted_into_the_area_are_quoted(self):
        verdict = area_verdict(85.0, "Mieszkanie", "Powierzchnia 85 m², w tym piwnica 6 m².")

        self.assertEqual([APPURTENANT_INCLUDED], verdict.flags)


if __name__ == "__main__":
    unittest.main()
