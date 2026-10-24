from __future__ import annotations

import unittest

from data.nuisances import (
    EXPRESSWAY, NEAR_EXPRESSWAY, NEAR_RAILWAY, RAILWAY, RUNWAY, UNDER_APPROACH, ApproachPaths, NuisanceCheck,
    features_from_overpass, nuisance_verdict, overpass_query, road_label,
)

_BALICE = ((50.0753999, 19.7680992), (50.0801982, 19.8026141))


def _way(way_id: int, tags: dict, points=((50.0, 19.9), (50.001, 19.901))) -> dict:
    return {"type": "way", "id": way_id, "tags": tags, "geometry": [{"lat": lat, "lon": lon} for lat, lon in points]}


class TestOverpassParsing(unittest.TestCase):

    def test_roads_railways_and_long_paved_runways_are_kept(self):
        features = features_from_overpass({"elements": [
            _way(1, {"highway": "motorway", "ref": "A4"}),
            _way(2, {"railway": "rail", "usage": "main", "name": "Kraków - Katowice"}),
            _way(3, {"aeroway": "runway", "surface": "concrete", "ref": "07/25"}, _BALICE),
        ]})

        self.assertEqual([EXPRESSWAY, RAILWAY, RUNWAY], [feature.kind for feature in features])
        self.assertEqual("A4", features[0].label)

    def test_tunnels_are_skipped_because_they_make_no_noise_above(self):
        self.assertEqual([], features_from_overpass({"elements": [
            _way(1, {"highway": "trunk", "ref": "S7", "tunnel": "yes"}),
        ]}))

    def test_grass_strips_and_short_runways_are_not_airports(self):
        self.assertEqual([], features_from_overpass({"elements": [
            _way(1, {"aeroway": "runway", "surface": "grass"}, _BALICE),
            _way(2, {"aeroway": "runway", "surface": "concrete"}, ((50.0853831, 19.9856079), (50.0832009, 19.99532))),
        ]}))

    def test_national_road_numbers_get_their_prefix(self):
        self.assertEqual("S7/DK52", road_label({"ref": "S7;52"}))
        self.assertEqual("A4", road_label({"ref": "A4;A4"}))
        self.assertEqual("Trasa Łagiewnicka", road_label({"name": "Trasa Łagiewnicka"}))

    def test_the_query_covers_the_bounding_box(self):
        self.assertIn("(49.90000,19.70000,50.20000,20.20000)", overpass_query(49.9, 19.7, 50.2, 20.2))


class TestApproachPaths(unittest.TestCase):

    def setUp(self):
        self.paths = ApproachPaths([("07/25", _BALICE)])

    def test_a_point_on_the_extended_centreline_is_under_the_approach(self):
        distance, label = self.paths.distance_beyond_runway(50.0897, 19.8716)

        self.assertAlmostEqual(5000, distance, delta=200)
        self.assertEqual("07/25", label)

    def test_a_point_beside_the_airport_is_not(self):
        self.assertIsNone(self.paths.distance_beyond_runway(50.1200, 19.7850))

    def test_the_approach_ends_after_eight_kilometres(self):
        self.assertIsNone(self.paths.distance_beyond_runway(50.1010, 19.9520))


class TestNuisanceVerdict(unittest.TestCase):

    def test_a_close_expressway_is_flagged_with_its_name(self):
        verdict = nuisance_verdict(NuisanceCheck(expressway_m=180, expressway_label="S52"))

        self.assertEqual([NEAR_EXPRESSWAY], verdict.flags)
        self.assertEqual(["droga S52 ok. 180 m od pinezki"], verdict.notes)

    def test_distances_beyond_the_thresholds_are_only_kept_as_numbers(self):
        verdict = nuisance_verdict(NuisanceCheck(expressway_m=900, railway_m=400))

        self.assertEqual([], verdict.flags)

    def test_railway_and_approach_are_flagged(self):
        verdict = nuisance_verdict(NuisanceCheck(railway_m=90, approach_m=4250, approach_label="07/25"))

        self.assertEqual([NEAR_RAILWAY, UNDER_APPROACH], verdict.flags)
        self.assertIn("ok. 4,2 km od jego końca", verdict.notes[1])

    def test_no_check_means_no_flags(self):
        self.assertEqual([], nuisance_verdict(None).flags)


if __name__ == "__main__":
    unittest.main()
