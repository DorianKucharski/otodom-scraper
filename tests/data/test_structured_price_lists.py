from __future__ import annotations

import json
import unittest
from datetime import date, datetime

from data.developer_price_lists import KnownList
from data.developer_prices import parse_price_list
from data.structured_price_lists import harvester_link

_NESTED_JSON = json.dumps({
    "dataSetName": "Oferta dewelopera ORION ZODIAK",
    "developer": {"name": "ORION ZODIAK", "address": "UL. PRZEMYSŁOWA 13, 30-701 KRAKÓW", "phoneNumber": "48123577778"},
    "offerDate": "2026-10-24",
    "investments": [{
        "investmentName": "Osiedle Zodiak",
        "city": "Kraków",
        "street": "Mariana Domagały",
        "salesOfficeAddress": "UL. PRZEMYSŁOWA 13, KRAKÓW",
        "buildings": [{
            "number": "39",
            "properties": [
                {"type": "Flat", "number": "1", "price": 609084.0, "area": 48.34, "pricePerMeter": 12600,
                 "priceHistory": [{"date": "2026-01-01", "price": 650000}]},
                {"type": "Flat", "number": "2", "price": 720000.0, "area": 55.1, "pricePerMeter": 13067},
            ],
        }],
    }],
}).encode()

_TABLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<opendata xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="x.xsd">
  <dataset status="published">
    <title><polish>Ceny mieszkań</polish></title>
    <resources><resource><dataDate>2026-10-25</dataDate><table>
      <row><developer_name>Elzam</developer_name><investment_street>Oboźna 2</investment_street>
        <investment_city>Elbląg</investment_city><unit_no>M.01</unit_no><area_m2>39.02</area_m2>
        <price_brutto>393321.6</price_brutto><price_m2_brutto>10080</price_m2_brutto>
        <lowest_price_30d_brutto>390000</lowest_price_30d_brutto></row>
      <row><developer_name>Elzam</developer_name><investment_street>Oboźna 2</investment_street>
        <investment_city>Elbląg</investment_city><unit_no>M.02</unit_no><area_m2>51.20</area_m2>
        <price_brutto>500000</price_brutto><price_m2_brutto>9766</price_m2_brutto>
        <lowest_price_30d_brutto>500000</lowest_price_30d_brutto></row>
    </table></resource></resources>
  </dataset>
</opendata>""".encode()

_HARVESTER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ns2:datasets xmlns:ns2="urn:otwarte-dane:harvester:1.13">
  <dataset><resources>
    <resource><url>https://example.pl/ceny-2026-10-23.csv</url><dataDate>2026-10-23</dataDate></resource>
    <resource><url>https://example.pl/ceny-2026-10-22.csv</url><dataDate>2026-10-22</dataDate></resource>
    <resource><url>https://example.pl/prospekt.pdf</url><dataDate>2026-10-24</dataDate></resource>
  </resources></dataset>
</ns2:datasets>""".encode()


class TestStructuredPriceLists(unittest.TestCase):

    def test_nested_json_units_inherit_the_investment_address(self):
        units = parse_price_list(_NESTED_JSON, "json")

        self.assertEqual(["1", "2"], [unit.unit for unit in units])
        first = units[0]
        self.assertEqual("Kraków", first.town)
        self.assertEqual("Mariana Domagały", first.street)
        self.assertEqual("39", first.building_number)
        self.assertEqual(609_084, first.price)
        self.assertEqual(12_600, first.price_per_m2)
        self.assertEqual(48.34, first.area)
        self.assertEqual(date(2026, 10, 24), first.price_since)

    def test_contact_fields_are_not_taken_for_the_unit_or_town(self):
        unit = parse_price_list(_NESTED_JSON, "json")[0]

        self.assertNotEqual("48123577778", unit.unit)
        self.assertEqual("Kraków", unit.town)

    def test_xml_table_rows_are_units(self):
        units = parse_price_list(_TABLE_XML, "xml")

        self.assertEqual(["M.01", "M.02"], [unit.unit for unit in units])
        self.assertEqual("Elbląg", units[0].town)
        self.assertEqual(393_322, units[0].price)
        self.assertEqual(10_080, units[0].price_per_m2)
        self.assertEqual(39.02, units[0].area)

    def test_a_harvester_feed_points_at_the_file_of_that_day(self):
        self.assertEqual(("https://example.pl/ceny-2026-10-22.csv", "csv"),
                         harvester_link(_HARVESTER_XML, date(2026, 10, 22)))
        self.assertEqual(("https://example.pl/ceny-2026-10-23.csv", "csv"), harvester_link(_HARVESTER_XML, None))

    def test_a_harvester_feed_has_no_units_of_its_own(self):
        self.assertEqual([], parse_price_list(_HARVESTER_XML, "xml"))

    def test_broken_files_give_nothing(self):
        self.assertEqual([], parse_price_list(b"{not json", "json"))
        self.assertEqual([], parse_price_list(b"<a><b>", "xml"))


class TestKnownListRecheck(unittest.TestCase):

    def test_a_list_rejected_for_a_format_that_is_now_parsed_is_checked_again(self):
        recheck_before = datetime(2026, 9, 25)
        fresh = datetime(2026, 10, 25)

        self.assertTrue(KnownList(False, None, fresh, "format json").due(recheck_before))
        self.assertFalse(KnownList(False, None, fresh, "format pdf").due(recheck_before))
        self.assertFalse(KnownList(False, None, fresh).due(recheck_before))
        self.assertTrue(KnownList(False, None, datetime(2026, 9, 1)).due(recheck_before))


if __name__ == "__main__":
    unittest.main()
