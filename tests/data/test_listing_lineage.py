from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from data.listing_lineage import ListingRow, ListingText, build_groups, words_of

_NOW = datetime(2026, 10, 24)


def _listing(listing_id: int, **overrides) -> ListingRow:
    values = dict(
        id=listing_id,
        owner_id=7,
        market="SECONDARY",
        offer_type="SALE",
        object_type="APARTMENT",
        created_at=datetime(2026, 4, 27),
        ended_at=None,
        ended_at_known=True,
        price=1_099_000,
        area=120.0,
        rooms=4,
        floor="FLOOR_1",
        building_year=2011,
        latitude=50.1100,
        longitude=19.8876,
        city_id=38,
        title="4M| ogród_balkon_2xmp_klima| TYLKO U NAS!",
    )
    values.update(overrides)
    return ListingRow(**values)


def _texts(texts: dict[int, tuple[str, str]]):
    def load(ids):
        return {
            ad_id: ListingText(title=words_of(title), description=words_of(description))
            for ad_id, (title, description) in texts.items()
            if ad_id in set(ids)
        }
    return load


def _no_texts(ids):
    return {}


class TestListingLineage(unittest.TestCase):

    def test_an_agency_relisting_the_same_flat_every_month_forms_one_chain(self):
        listings = [
            _listing(1, created_at=datetime(2026, 4, 27), ended_at=datetime(2026, 5, 5), ended_at_known=False),
            _listing(2, created_at=datetime(2026, 6, 29), ended_at=datetime(2026, 10, 11), ended_at_known=False,
                     latitude=50.1104),
            _listing(3, created_at=datetime(2026, 7, 29), ended_at=datetime(2026, 10, 11), ended_at_known=False,
                     longitude=19.8930),
            _listing(4, created_at=datetime(2026, 9, 29)),
        ]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertEqual([1, 2, 3, 4], groups[4].member_ids)
        self.assertEqual(1, groups[4].group_id)

    def test_identical_units_of_a_development_offered_at_the_same_time_stay_separate(self):
        listings = [
            _listing(1, market="PRIMARY", title="Bukowa - 05.1", price=992_962),
            _listing(2, market="PRIMARY", title="Bukowa - 06.1", price=994_223),
        ]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertEqual([1], groups[1].member_ids)
        self.assertEqual([2], groups[2].member_ids)

    def test_a_flat_moving_from_its_owner_to_an_agency_is_linked_by_its_description(self):
        description = "Dwupoziomowe mieszkanie na zamkniętym osiedlu, ogród, dwa miejsca postojowe, klimatyzacja"
        listings = [
            _listing(1, owner_id=1, created_at=datetime(2025, 12, 2), ended_at=datetime(2026, 4, 17), price=1_029_000),
            _listing(2, owner_id=2, created_at=datetime(2026, 4, 27), price=1_099_000),
        ]
        texts = {1: ("Apartament 120 m2", description), 2: ("4M ogród balkon", description + " tylko u nas")}

        groups = build_groups(listings, _texts(texts), _NOW)

        self.assertEqual([1, 2], groups[2].member_ids)

    def test_two_owners_listing_similar_flats_at_the_same_time_are_not_merged(self):
        listings = [
            _listing(1, owner_id=1),
            _listing(2, owner_id=2, created_at=datetime(2026, 5, 1)),
        ]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertEqual([1], groups[1].member_ids)

    def test_a_different_area_breaks_the_link(self):
        listings = [
            _listing(1, ended_at=datetime(2026, 5, 1)),
            _listing(2, area=96.7, created_at=datetime(2026, 6, 1)),
        ]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertEqual([2], groups[2].member_ids)

    def test_far_apart_listings_are_not_linked(self):
        listings = [
            _listing(1, ended_at=datetime(2026, 5, 1)),
            _listing(2, latitude=50.20, created_at=datetime(2026, 6, 1)),
        ]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertEqual([2], groups[2].member_ids)

    def test_a_strong_first_to_last_match_does_not_cut_the_middle_of_the_chain(self):
        description = "Dwupoziomowy apartament na zamkniętym osiedlu z ogrodem i klimatyzacją"
        listings = [
            _listing(1, created_at=datetime(2026, 4, 27), ended_at=datetime(2026, 5, 5), ended_at_known=False),
            _listing(2, created_at=datetime(2026, 6, 29), ended_at=datetime(2026, 10, 11), ended_at_known=False),
            _listing(3, created_at=datetime(2026, 9, 29)),
        ]
        texts = {1: ("4M ogród", description), 2: ("4M DUŻY ogród", "***"), 3: ("4M ogród", description)}

        groups = build_groups(listings, _texts(texts), _NOW)

        self.assertEqual([1, 2, 3], groups[3].member_ids)

    def test_two_units_live_together_never_end_up_in_one_group_through_an_earlier_listing(self):
        listings = [
            _listing(1, owner_id=1, ended_at=datetime(2026, 5, 1)),
            _listing(2, owner_id=1, created_at=datetime(2026, 6, 1), price=1_100_000),
            _listing(3, owner_id=1, created_at=datetime(2026, 6, 2), price=1_090_000),
        ]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertNotEqual(groups[2].group_id, groups[3].group_id)

    def test_listings_without_area_stay_alone(self):
        listings = [_listing(1, area=None), _listing(2, area=None, created_at=datetime(2026, 6, 1))]

        groups = build_groups(listings, _no_texts, _NOW)

        self.assertEqual([1], groups[1].member_ids)


    def test_a_series_of_similar_units_posted_together_is_not_one_flat(self):
        listings = [
            _listing(index, market="PRIMARY", price=700_000 + index * 1_000, created_at=datetime(2026, 9, 10) + timedelta(days=index),
                     ended_at=datetime(2026, 10, 11), ended_at_known=False)
            for index in range(1, 6)
        ]
        texts = {index: ("3 pok balkon DNI OTWARTE", "Nowa inwestycja z halą garażową") for index in range(1, 6)}

        groups = build_groups(listings, _texts(texts), _NOW)

        self.assertEqual(5, len({group.group_id for group in groups.values()}))


class TestWords(unittest.TestCase):

    def test_html_and_short_words_are_ignored(self):
        self.assertEqual(frozenset({"ogród", "balkon"}), words_of("<p>4M| ogród_balkon</p>"))


if __name__ == "__main__":
    unittest.main()
