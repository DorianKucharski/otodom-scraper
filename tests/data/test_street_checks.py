from __future__ import annotations

import unittest

from data.location_checks import LocationVerdict
from data.street_checks import PIN_FAR_FROM_STREET, StreetCheck, street_key, street_verdict, streets_from_overpass


class TestStreetKey(unittest.TestCase):

    def test_the_surname_identifies_the_street(self):
        self.assertEqual("bogdanowskiego", street_key("ul. Wincentego Bogdanowskiego"))
        self.assertEqual("laszkiewicza", street_key("ul. płk. pil. Stefana Łaszkiewicza"))

    def test_house_numbers_are_ignored(self):
        self.assertEqual("wielicka", street_key("Wielicka 109/12"))

    def test_kraków_osiedla_are_areas_not_streets(self):
        self.assertIsNone(street_key("os. Józefa Strusia"))
        self.assertIsNone(street_key("Osiedle Dywizjonu 303"))

    def test_masked_and_missing_streets_have_no_key(self):
        self.assertIsNone(street_key("***"))
        self.assertIsNone(street_key(None))

    def test_overpass_ways_keep_their_key(self):
        streets = streets_from_overpass({"elements": [
            {"id": 1, "tags": {"name": "Wincentego Bogdanowskiego"}, "geometry": [{"lat": 50.0, "lon": 19.9}, {"lat": 50.001, "lon": 19.9}]},
            {"id": 2, "tags": {"name": "Rynek Główny"}, "geometry": [{"lat": 50.0, "lon": 19.9}, {"lat": 50.001, "lon": 19.9}]},
        ]})

        self.assertEqual([(1, "Wincentego Bogdanowskiego", "bogdanowskiego")], [street[:3] for street in streets])


class TestStreetVerdict(unittest.TestCase):

    def test_a_pin_two_kilometres_from_its_street_is_flagged(self):
        verdict = LocationVerdict()

        self.assertTrue(street_verdict(StreetCheck("ul. Wincentego Bogdanowskiego", 1984), verdict))
        self.assertEqual([PIN_FAR_FROM_STREET], verdict.flags)
        self.assertIn("ok. 2,0 km od pinezki", verdict.notes[0])

    def test_a_pin_on_a_long_street_is_fine(self):
        verdict = LocationVerdict()

        self.assertFalse(street_verdict(StreetCheck("Wielicka", 640), verdict))
        self.assertEqual([], verdict.flags)

    def test_a_namesake_street_in_another_town_is_not_a_misplaced_pin(self):
        verdict = LocationVerdict()

        self.assertFalse(street_verdict(StreetCheck("ul. Franciszkańska", 55_353), verdict))


if __name__ == "__main__":
    unittest.main()
