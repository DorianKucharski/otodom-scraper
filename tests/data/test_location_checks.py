from __future__ import annotations

import unittest

from data.location_checks import (
    BORDER_IN_TEXT, LINEAGE_CITY_MISMATCH, NEAR_CITY_BORDER, OTHER_PLACE_IN_TEXT, PIN_OUTSIDE_CITY, LocationVerdict,
    PinCheck, PlaceCentre, PlaceFinder, lineage_verdict, pin_verdict, text_verdict,
)

_GAIK = (50.10999, 19.887625)
_PLACES = PlaceFinder([
    PlaceCentre(city_id=7526, name="Modlnica", latitude=50.1300, longitude=19.8700),
    PlaceCentre(city_id=108, name="Zielonki", latitude=50.1200, longitude=19.9200),
    PlaceCentre(city_id=1, name="Wieliczka", latitude=49.9870, longitude=20.0650),
    PlaceCentre(city_id=38, name="Kraków", latitude=50.0600, longitude=19.9400),
])


def _check(inside: bool, border_m: int, town: bool = True, area_km2: float = 327) -> PinCheck:
    return PinCheck(ad_id=1, claimed_is_town=town, claimed_area_km2=area_km2, inside_claimed=inside, border_m=border_m,
                    pin_city_name="Kraków" if inside else None, pin_gmina_name="Kraków" if inside else "Wielka Wieś")


class TestPinVerdict(unittest.TestCase):

    def test_a_pin_close_to_the_city_border_is_flagged(self):
        verdict = LocationVerdict()

        pin_verdict("Kraków", _check(inside=True, border_m=835), verdict)

        self.assertEqual([NEAR_CITY_BORDER], verdict.flags)
        self.assertIn("835 m", verdict.notes[0])

    def test_a_pin_outside_the_claimed_city_is_flagged_with_its_real_gmina(self):
        verdict = LocationVerdict()

        pin_verdict("Kraków", _check(inside=False, border_m=289), verdict)

        self.assertEqual([PIN_OUTSIDE_CITY], verdict.flags)
        self.assertIn("Wielka Wieś", verdict.notes[0])

    def test_the_border_of_a_small_town_is_not_worth_a_flag(self):
        verdict = LocationVerdict()

        pin_verdict("Skawina", _check(inside=True, border_m=600, area_km2=20), verdict)

        self.assertEqual([], verdict.flags)

    def test_a_pin_deep_inside_the_city_is_fine(self):
        verdict = LocationVerdict()

        pin_verdict("Kraków", _check(inside=True, border_m=5000), verdict)

        self.assertEqual([], verdict.flags)

    def test_villages_have_no_town_boundary_to_check(self):
        verdict = LocationVerdict()

        pin_verdict("Modlnica", _check(inside=False, border_m=10, town=False), verdict)

        self.assertEqual([], verdict.flags)


class TestTextVerdict(unittest.TestCase):

    def test_a_nearby_village_named_in_the_description_is_flagged(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Apartament", "Spokojna okolica w Modlnicy, blisko obwodnicy.", _PLACES, verdict)

        self.assertEqual([OTHER_PLACE_IN_TEXT], verdict.flags)
        self.assertIn("Modlnica", verdict.notes[0])
        self.assertIn("Modlnicy", verdict.notes[0])

    def test_a_distant_town_does_not_count(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Apartament", "Do Wieliczki dojedziesz w 30 minut.", _PLACES, verdict)

        self.assertEqual([], verdict.flags)

    def test_the_claimed_city_itself_does_not_count(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Apartament w Krakowie", "Kraków, Prądnik Biały.", _PLACES, verdict)

        self.assertEqual([], verdict.flags)

    def test_a_border_phrase_is_quoted(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Apartament 120 m2, 1 km od granicy Krakowa", None, _PLACES, verdict)

        self.assertEqual([BORDER_IN_TEXT], verdict.flags)
        self.assertIn("1 km od granicy Krakowa", verdict.notes[0])

    def test_a_named_gmina_is_quoted(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Dom", "Podatki płacisz w gminie Zielonki.", _PLACES, verdict)

        self.assertIn(BORDER_IN_TEXT, verdict.flags)


    def test_travel_times_to_neighbouring_towns_do_not_count(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Mieszkanie", "Do Zielonek 5 min, Modlnica – 3 km.", _PLACES, verdict)

        self.assertEqual([], verdict.flags)

    def test_a_word_sharing_the_stem_is_not_a_place(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Mieszkanie", "Zielone dachy i dużo drzew.", _PLACES, verdict)

        self.assertEqual([], verdict.flags)

    def test_the_border_of_a_district_or_a_country_does_not_count(self):
        for description in ("Mieszkanie na granicy dzielnic.", "Dom przy granicy z Czechami.",
                            "Blok przy granicy z Krowodrzą."):
            verdict = LocationVerdict()

            text_verdict("Kraków", *_GAIK, "Mieszkanie", description, _PLACES, verdict, district_names=["Krowodrza"])

            self.assertEqual([], verdict.flags, description)

    def test_the_gmina_of_the_claimed_town_itself_does_not_count(self):
        verdict = LocationVerdict()

        text_verdict("Pieniężno", *_GAIK, "Dom", "Położony w gminie Pieniężno.", _PLACES, verdict)

        self.assertEqual([], verdict.flags)

    def test_living_under_the_claimed_city_is_flagged(self):
        verdict = LocationVerdict()

        text_verdict("Kraków", *_GAIK, "Bliźniak pod Krakowem", None, _PLACES, verdict)

        self.assertEqual([BORDER_IN_TEXT], verdict.flags)


class TestLineageVerdict(unittest.TestCase):

    def test_another_listing_of_the_flat_naming_a_different_place_is_flagged(self):
        verdict = LocationVerdict()

        lineage_verdict("Kraków", ["Modlnica", "Kraków", None], verdict)

        self.assertEqual([LINEAGE_CITY_MISMATCH], verdict.flags)
        self.assertIn("Modlnica", verdict.notes[0])


if __name__ == "__main__":
    unittest.main()
