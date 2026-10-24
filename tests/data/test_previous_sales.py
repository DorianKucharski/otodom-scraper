from __future__ import annotations

import unittest
from datetime import datetime

from data.previous_sales import FlatSale, PreviousSaleIndex, floor_number

_LISTED = datetime(2026, 9, 29)


def _sale(sale_id: int, area: float = 96.7, sold_at: datetime = datetime(2021, 9, 3), rooms=4,
          latitude: float = 50.12439, longitude: float = 19.88228, price: float = 694_000, floor=None) -> FlatSale:
    return FlatSale(id=sale_id, sold_at=sold_at, price=price, area=area, rooms=rooms, latitude=latitude,
                    longitude=longitude, floor=floor)


class TestPreviousSales(unittest.TestCase):

    def test_a_sale_of_the_same_area_next_to_the_pin_is_the_previous_sale(self):
        index = PreviousSaleIndex([_sale(1)])

        match = index.match(50.1245, 19.8824, 96.7, 4, _LISTED)

        self.assertEqual(694_000, match.price)
        self.assertEqual(datetime(2021, 9, 3), match.sold_at)
        self.assertLess(match.distance_m, 50)

    def test_the_latest_of_two_sales_wins(self):
        index = PreviousSaleIndex([_sale(1, sold_at=datetime(2015, 1, 7), price=425_000), _sale(2)])

        self.assertEqual(694_000, index.match(50.12439, 19.88228, 96.7, 4, _LISTED).price)

    def test_a_block_of_identical_flats_is_too_ambiguous(self):
        index = PreviousSaleIndex([_sale(index, sold_at=datetime(2020 + index, 1, 1)) for index in range(3)])

        self.assertIsNone(index.match(50.12439, 19.88228, 96.7, 4, _LISTED))

    def test_a_different_area_or_room_count_is_another_flat(self):
        index = PreviousSaleIndex([_sale(1, area=98.0), _sale(2, rooms=3)])

        self.assertIsNone(index.match(50.12439, 19.88228, 96.7, 4, _LISTED))

    def test_a_sale_after_the_listing_is_not_its_past(self):
        index = PreviousSaleIndex([_sale(1, sold_at=datetime(2026, 10, 1))])

        self.assertIsNone(index.match(50.12439, 19.88228, 96.7, 4, _LISTED))

    def test_a_round_area_does_not_identify_a_flat(self):
        index = PreviousSaleIndex([_sale(1, area=50.0)])

        self.assertIsNone(index.match(50.12439, 19.88228, 50.0, 4, _LISTED))

    def test_an_implausible_price_is_another_flat_or_a_data_error(self):
        index = PreviousSaleIndex([_sale(1, price=1_081_094, area=33.07)])

        self.assertIsNone(index.match(50.12439, 19.88228, 33.07, 4, _LISTED, price=496_050))

    def test_a_flat_on_another_floor_is_another_flat(self):
        index = PreviousSaleIndex([_sale(1, floor=6), _sale(2, floor=2, price=739_000)])

        self.assertEqual(739_000, index.match(50.12439, 19.88228, 96.7, 4, _LISTED, floor=2).price)

    def test_floor_codes_become_numbers(self):
        self.assertEqual(0, floor_number("GROUND_FLOOR"))
        self.assertEqual(3, floor_number("FLOOR_3"))
        self.assertIsNone(floor_number("GARRET"))

    def test_a_sale_far_from_the_pin_does_not_count(self):
        index = PreviousSaleIndex([_sale(1, latitude=50.1300)])

        self.assertIsNone(index.match(50.12439, 19.88228, 96.7, 4, _LISTED))


if __name__ == "__main__":
    unittest.main()
