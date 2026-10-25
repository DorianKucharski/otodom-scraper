from __future__ import annotations

import unittest
from datetime import datetime

from data.developer_matches import DeveloperUnitIndex, DeveloperUnitRow


def _unit(id: int, **overrides) -> DeveloperUnitRow:
    values = dict(
        id=id, institution_id=7, dataset_id=70, developer="MJM", investment="Conrada 27", town="Kraków",
        street="ul. Józefa Conrada", building_number="27", unit=f"B.{id}", area=68.0, rooms=3, price=998_000,
        price_per_m2=14_676, price_since=datetime(2026, 10, 17), price_with_extras=None, extras=(),
        first_seen=datetime(2025, 9, 11), last_seen=datetime(2026, 10, 24), first_price=1_017_600,
        highest_price=1_017_600,
    )
    values.update(overrides)
    return DeveloperUnitRow(**values)


class TestDeveloperUnitIndex(unittest.TestCase):

    def test_an_ad_on_the_same_street_with_the_same_area_matches(self):
        index = DeveloperUnitIndex([_unit(1), _unit(2, area=54.2, price=800_000)])

        match = index.match("Kraków", "conrada", 68.0, 3, 1_050_000)

        self.assertEqual("B.1", match.unit.unit)
        self.assertEqual("Conrada 27, ul. Józefa Conrada 27, Kraków", match.investment_label)

    def test_another_developer_on_the_same_street_is_not_taken_for_the_unit(self):
        index = DeveloperUnitIndex([_unit(1, price=686_550, first_price=686_550, highest_price=686_550)])

        self.assertIsNone(index.match("Kraków", "conrada", 68.0, 3, 950_300))

    def test_without_a_street_the_price_has_to_agree(self):
        index = DeveloperUnitIndex([_unit(1)])

        self.assertIsNotNone(index.match("Kraków", None, 68.0, None, 1_000_000))
        self.assertIsNone(index.match("Kraków", None, 68.0, None, 1_100_000))

    def test_a_different_town_or_area_does_not_match(self):
        index = DeveloperUnitIndex([_unit(1)])

        self.assertIsNone(index.match("Wieliczka", "conrada", 68.0, 3, 998_000))
        self.assertIsNone(index.match("Kraków", "conrada", 68.3, 3, 998_000))

    def test_a_different_room_count_breaks_a_street_only_match(self):
        index = DeveloperUnitIndex([_unit(1)])

        self.assertIsNone(index.match("Kraków", "conrada", 68.0, 2, 1_200_000))

    def test_identical_units_of_one_investment_still_match(self):
        index = DeveloperUnitIndex([_unit(1), _unit(2)])

        self.assertIsNotNone(index.match("Kraków", "conrada", 68.0, 3, 998_000))

    def test_two_developers_with_the_same_unit_are_ambiguous(self):
        index = DeveloperUnitIndex([_unit(1, street=None), _unit(2, institution_id=8, street=None)])

        self.assertIsNone(index.match("Kraków", None, 68.0, 3, 998_000))

    def test_a_unit_missing_from_the_newest_list_is_gone(self):
        index = DeveloperUnitIndex([_unit(1, last_seen=datetime(2026, 8, 1)), _unit(2, area=54.2)])

        match = index.match("Kraków", "conrada", 68.0, 3, 998_000)

        self.assertTrue(match.gone)
        self.assertEqual(1, match.investment.listed)
        self.assertEqual(1, match.investment.gone)
        self.assertEqual(datetime(2025, 9, 11), match.investment.tracked_since)


if __name__ == "__main__":
    unittest.main()
