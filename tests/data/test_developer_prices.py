from __future__ import annotations

import unittest
from datetime import date

from data.developer_price_lists import Resource, in_places, same_area, sampled
from data.developer_prices import parse_price_list, place_name, units_from_rows

_TEMPLATE_HEADER = [
    "Nazwa dewelopera",
    "Miejscowość adresu lokalu, w którym prowadzona jest sprzedaż",
    "Gmina lokalizacji przedsięwzięcia deweloperskiego lub zadania inwestycyjnego",
    "Miejscowość lokalizacji przedsięwzięcia deweloperskiego lub zadania inwestycyjnego",
    "Ulica lokalizacji przedsięwzięcia deweloperskiego lub zadania inwestycyjnego",
    "Nr nieruchomości lokalizacji przedsięwzięcia deweloperskiego lub zadania inwestycyjnego",
    "Rodzaj nieruchomości: lokal mieszkalny, dom jednorodzinny ",
    "Nr lokalu lub domu jednorodzinnego nadany przez dewelopera",
    "Cena m 2 powierzchni użytkowej lokalu mieszkalnego / domu jednorodzinnego [zł]",
    "Data od której cena obowiązuje cena m 2 powierzchni użytkowej lokalu mieszkalnego / domu jednorodzinnego",
    "Cena lokalu mieszkalnego lub domu jednorodzinnego będących przedmiotem umowy stanowiąca iloczyn ceny m2 oraz "
    "powierzchni [zł]",
    "Cena lokalu mieszkalnego lub domu jednorodzinnego uwzględniająca cenę lokalu stanowiącą iloczyn powierzchni oraz "
    "metrażu i innych składowych ceny, o których mowa w art. 19a ust. 1 pkt 1), 2) lub 3) [zł]",
    "Rodzaj części nieruchomości będących przedmiotem umowy",
    "Oznaczenie części nieruchomości nadane przez dewelopera",
    "Cena części nieruchomości, będących przedmiotem umowy [zł]",
]


def _row(unit="B.93", price=998000, per_m2="14 679,41", extra_kind="X", extra_price="X"):
    return ["MJM", "Warszawa", "Kraków", "Kraków", "ul. Józefa Conrada", "27", "Lokal mieszkalny", unit, per_m2,
            "2026-10-17 00:00:00", price, "X", extra_kind, "MP 12", extra_price]


class TestPriceListParsing(unittest.TestCase):

    def test_the_ministry_template_is_read_by_its_column_names(self):
        unit = next(units_from_rows([_TEMPLATE_HEADER, _row()]))

        self.assertEqual("Kraków", unit.town)
        self.assertEqual("ul. Józefa Conrada", unit.street)
        self.assertEqual("B.93", unit.unit)
        self.assertEqual(998_000, unit.price)
        self.assertEqual(14_679, unit.price_per_m2)
        self.assertEqual(date(2026, 10, 17), unit.price_since)
        self.assertIsNone(unit.price_with_extras)

    def test_the_sales_office_town_is_not_taken_for_the_investment(self):
        unit = next(units_from_rows([_TEMPLATE_HEADER, _row()]))

        self.assertNotEqual("Warszawa", unit.town)

    def test_the_area_is_derived_from_the_price_and_the_price_per_metre(self):
        unit = next(units_from_rows([_TEMPLATE_HEADER, _row()]))

        self.assertAlmostEqual(67.99, unit.area, places=1)

    def test_extra_parts_are_kept_with_their_price(self):
        unit = next(units_from_rows([_TEMPLATE_HEADER, _row(extra_kind="miejsce postojowe", extra_price="45 000,00 zł")]))

        self.assertEqual(["miejsce postojowe MP 12: 45 000,00 zł"], unit.extras)
        self.assertEqual(45_000, unit.extras_value)

    def test_a_unit_listed_twice_for_two_parts_is_one_unit(self):
        rows = [_TEMPLATE_HEADER, _row(extra_kind="miejsce postojowe", extra_price="45000"),
                _row(extra_kind="komórka lokatorska", extra_price="15000")]

        units = list(units_from_rows(rows))

        self.assertEqual(1, len(units))
        self.assertEqual(2, len(units[0].extras))

    def test_rows_without_a_unit_label_are_skipped(self):
        self.assertEqual([], list(units_from_rows([_TEMPLATE_HEADER, _row(unit="X")])))

    def test_a_header_below_a_title_row_is_found(self):
        units = list(units_from_rows([["Cennik na dzień 2026-10-24"], _TEMPLATE_HEADER, _row()]))

        self.assertEqual(1, len(units))

    def test_a_shortened_csv_header_with_area_and_rooms_is_read(self):
        content = (
            '"Nazwa dewelopera";"Miejscowość lokalizacji przedsięwzięcia lub zadania";"Ulica lokalizacji przedsięwzięcia lub zadania";'
            '"Nr nieruchomości nadany przez dewelopera";"Powierzchnia";"Liczba pokoi";"Cena za m2 nieruchomości";'
            '"Cena nieruchomości"\n'
            '"TCH";"Cegielnia";"Wawrzyna";"20/1";"54.40";"2";"9007.35";"490000"\n'
        ).encode("utf-8-sig")

        unit = parse_price_list(content, "csv")[0]

        self.assertEqual("20/1", unit.unit)
        self.assertEqual(54.4, unit.area)
        self.assertEqual(2, unit.rooms)
        self.assertEqual(490_000, unit.price)

    def test_polish_and_english_number_formats_are_read(self):
        unit = next(units_from_rows([_TEMPLATE_HEADER, _row(price="1.234.567,00", per_m2="12,345.50")]))

        self.assertEqual(1_234_567, unit.price)
        self.assertEqual(12_346, unit.price_per_m2)

    def test_unsupported_formats_give_nothing(self):
        self.assertEqual([], parse_price_list(b"<xml/>", "xml"))


class TestPlaces(unittest.TestCase):

    def test_place_names_drop_accents_and_administrative_prefixes(self):
        self.assertEqual("krakow", place_name("m. Kraków"))
        self.assertEqual("wielka wies", place_name("Gmina Wielka Wieś"))

    def test_a_village_is_kept_through_its_gmina(self):
        unit = next(units_from_rows([_TEMPLATE_HEADER, _row()]))
        unit.town, unit.gmina = "Modlnica", "Wielka Wieś"

        self.assertTrue(in_places(unit, {"wielka wies"}))
        self.assertFalse(in_places(unit, {"krakow"}))


class TestSampling(unittest.TestCase):

    def __resources(self, *days: int) -> list[Resource]:
        return [Resource(day, date(2026, 1, 1).replace(day=day), "xlsx", f"https://example/{day}") for day in days]

    def test_history_is_sampled_with_the_newest_file_always_kept(self):
        picked = sampled(self.__resources(1, 2, 3, 9, 10, 20), None, 7)

        self.assertEqual([1, 9, 20], [resource.data_date.day for resource in picked])

    def test_a_unit_number_reused_for_another_area_is_another_flat(self):
        self.assertTrue(same_area(29.77, 29.80))
        self.assertFalse(same_area(51.67, 29.77))
        self.assertTrue(same_area(None, 29.77))

    def test_only_files_after_the_processed_date_are_taken(self):
        picked = sampled(self.__resources(1, 2, 3), date(2026, 1, 2), 7)

        self.assertEqual([3], [resource.data_date.day for resource in picked])


if __name__ == "__main__":
    unittest.main()
