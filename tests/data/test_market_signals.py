from __future__ import annotations

import unittest
from datetime import datetime

from data.comparables import ComparableRow
from data.listing_lineage import ListingGroup, ListingRow
from data.market_signals import AdFacts, TransactionIndex, group_history

_NOW = datetime(2026, 10, 24)


def _listing(listing_id: int, **overrides) -> ListingRow:
    values = dict(
        id=listing_id, owner_id=7, market="SECONDARY", offer_type="SALE", object_type="APARTMENT",
        created_at=datetime(2026, 4, 27), ended_at=None, ended_at_known=True, price=1_099_000, area=120.0,
        rooms=4, floor="FLOOR_1", building_year=2011, latitude=50.06, longitude=19.94, city_id=38,
        title="Mieszkanie 4 pokoje",
    )
    values.update(overrides)
    return ListingRow(**values)


def _facts(listing: ListingRow) -> AdFacts:
    return AdFacts(listing=listing, status="active" if listing.active else "outdated", city_name="Kraków",
                   last_seen_at=listing.ended_at or _NOW)


class TestGroupHistory(unittest.TestCase):

    def test_an_active_relisted_flat_counts_days_from_its_first_listing(self):
        first = _listing(1, created_at=datetime(2025, 12, 2), ended_at=datetime(2026, 4, 17), owner_id=1)
        second = _listing(2, created_at=datetime(2026, 4, 27), owner_id=2)
        group = ListingGroup(group_id=1, member_ids=[1, 2])
        observations = {1: [(datetime(2025, 12, 2), 1_079_000), (datetime(2026, 3, 1), 1_029_000)],
                        2: [(datetime(2026, 4, 27), 1_099_000)]}

        history = group_history(group, {1: _facts(first), 2: _facts(second)}, observations, _NOW)

        self.assertEqual(datetime(2025, 12, 2), history.first_listed_at)
        self.assertEqual((_NOW - datetime(2025, 12, 2)).days, history.days_on_market)
        self.assertEqual(1_079_000, history.first_price)
        self.assertEqual(1_029_000, history.lowest_price)
        self.assertEqual(1_099_000, history.highest_price)
        self.assertEqual(2, history.advertisers_count)

    def test_a_removed_flat_stops_counting_when_it_was_last_seen(self):
        only = _listing(1, created_at=datetime(2026, 1, 1), ended_at=datetime(2026, 3, 1))
        group = ListingGroup(group_id=1, member_ids=[1])

        history = group_history(group, {1: _facts(only)}, {}, _NOW)

        self.assertEqual(59, history.days_on_market)


class TestTransactionIndex(unittest.TestCase):

    def __index(self) -> TransactionIndex:
        return TransactionIndex([
            ComparableRow(id=index, group_id=-index, offer_type="SECONDARY", object_type=None,
                          latitude=50.06 + index * 0.0001, longitude=19.94, area=100.0, price_per_m2=14_000)
            for index in range(1, 11)
        ])

    def test_a_flat_is_compared_with_flat_sales(self):
        stats = self.__index().stats_for(_listing(1, area=100.0, price=1_200_000))

        self.assertEqual(14_000, stats.median_price_per_m2)

    def test_a_house_listed_among_flats_is_not_compared_with_flat_sales(self):
        for listing in (
            _listing(1, area=100.0, title="Bliźniak po remoncie"),
            _listing(1, area=100.0, building_type="DETACHED"),
            _listing(1, area=234.0),
        ):
            self.assertIsNone(self.__index().stats_for(listing))


if __name__ == "__main__":
    unittest.main()
