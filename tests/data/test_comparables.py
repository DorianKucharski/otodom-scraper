from __future__ import annotations

import unittest

from data.comparables import MIN_COMPARABLES, ComparableRow, ComparablesIndex, bounded_pct


def _row(row_id: int, latitude: float = 50.0600, longitude: float = 19.9400, area: float = 60.0,
         price_per_m2: float = 15_000, group_id: int | None = None, object_type: str = "APARTMENT") -> ComparableRow:
    return ComparableRow(
        id=row_id,
        group_id=group_id if group_id is not None else row_id,
        offer_type="SALE",
        object_type=object_type,
        latitude=latitude,
        longitude=longitude,
        area=area,
        price_per_m2=price_per_m2,
    )


def _neighbourhood(count: int, price_per_m2: float = 15_000, area: float = 60.0, offset: float = 0.0001):
    return [_row(100 + index, latitude=50.06 + index * offset, area=area, price_per_m2=price_per_m2)
            for index in range(count)]


class TestComparables(unittest.TestCase):

    def test_the_median_comes_from_nearby_listings_of_similar_size(self):
        index = ComparablesIndex(_neighbourhood(MIN_COMPARABLES, price_per_m2=15_000))

        stats = index.stats_for(_row(1, price_per_m2=9_000))

        self.assertEqual(15_000, stats.median_price_per_m2)
        self.assertEqual(750, stats.radius_m)
        self.assertEqual(-40.0, stats.difference_pct(9_000))

    def test_much_bigger_flats_are_not_compared(self):
        index = ComparablesIndex(_neighbourhood(MIN_COMPARABLES, area=200))

        self.assertIsNone(index.stats_for(_row(1, area=60)))

    def test_the_radius_grows_until_there_are_enough_listings(self):
        index = ComparablesIndex(_neighbourhood(MIN_COMPARABLES, offset=0.005))

        stats = index.stats_for(_row(1))

        self.assertGreater(stats.radius_m, 750)

    def test_relistings_of_one_flat_count_once(self):
        relistings = [_row(100 + index, group_id=100) for index in range(MIN_COMPARABLES)]

        self.assertIsNone(ComparablesIndex(relistings).stats_for(_row(1)))

    def test_the_listing_itself_is_not_its_own_comparable(self):
        rows = _neighbourhood(MIN_COMPARABLES - 1) + [_row(1)]

        self.assertIsNone(ComparablesIndex(rows).stats_for(_row(1)))

    def test_houses_are_not_compared_with_flats(self):
        index = ComparablesIndex(_neighbourhood(MIN_COMPARABLES))

        self.assertIsNone(index.stats_for(_row(1, object_type="HOUSE")))

    def test_a_typo_in_the_price_reports_no_percentage(self):
        index = ComparablesIndex(_neighbourhood(MIN_COMPARABLES))
        stats = index.stats_for(_row(1))

        self.assertIsNone(stats.difference_pct(15_000_000))
        self.assertEqual(-20.0, stats.difference_pct(12_000))

    def test_percentages_beyond_the_column_range_are_dropped(self):
        self.assertEqual(999.0, bounded_pct(999))
        self.assertIsNone(bounded_pct(-1000.4))


if __name__ == "__main__":
    unittest.main()
