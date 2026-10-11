from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime

from data.ad_dto import AdDto, AddressDto, CityDto, CoordinatesDto, LocationDto, LocationHintsDto, PriceDto
from data.location_resolver import LocationIndex, complete_location, synthetic_location_id
from data.models import Ad
from data.raw_payload import as_page_json, compress_payload, decompress_payload

_EMPTY_ADDRESS = {
    "street": {"name": "ul. Henryka Pachońskiego", "number": None},
    "subdistrict": None, "district": None, "city": None, "county": None,
    "municipality": None, "province": None, "postalCode": None,
}

_LOCATION = {
    "coordinates": {"latitude": 50.094364, "longitude": 19.925657},
    "reverseGeocoding": {"locations": [
        {"id": "malopolskie", "locationLevel": "voivodeship", "name": "małopolskie"},
        {"id": "malopolskie/krakow/krakow/krakow", "locationLevel": "city_or_village", "name": "Kraków"},
        {"id": "malopolskie/krakow/krakow/krakow/pradnik-bialy", "locationLevel": "district", "name": "Prądnik Biały"},
        {"id": "malopolskie/krakow/krakow/krakow/pradnik-bialy/pradnik-bialy-zachod",
         "locationLevel": "residential", "name": "Prądnik Biały Zachód"},
    ]},
    "address": _EMPTY_ADDRESS,
}

_TRACKING = {"city_id": "38", "city_name": "krakow", "region_id": "malopolskie", "subregion_id": "powiat-krakow"}


def _page(location: dict = _LOCATION, tracking: dict = _TRACKING) -> dict:
    return {"props": {"pageProps": {
        "ad": {
            "id": 68512288, "publicId": "4DtaU", "slug": "2-pokoje", "url": "https://www.otodom.pl/pl/oferta/x",
            "title": "2 pokoje", "description": "", "createdAt": "2026-10-10T07:00:35Z",
            "modifiedAt": "2026-10-10T07:00:35Z", "status": "active", "market": "PRIMARY",
            "advertiserType": "business", "target": {"Price": 600000, "Price_per_m": 19700},
            "location": location, "owner": {"id": 1, "name": "Biuro", "type": "agency"},
        },
        "adTrackingData": tracking,
        "developmentData": None,
        "currentUser": {"secret": "not stored"},
    }}}


def _index() -> LocationIndex:
    return LocationIndex.build(
        provinces=[(6, "malopolskie")],
        counties=[(410, "powiat-krakow")],
        city_ids=[38],
        districts=[(65, "pradnik-bialy"), (71, "zwierzyniec"), (23659, "zwierzyniec")],
        district_usage=[(38, "pradnik-bialy", 65, 900), (38, "zwierzyniec", 71, 400), (991, "zwierzyniec", 23659, 3)],
    )


class TestLocationHints(unittest.TestCase):

    def test_hints_come_from_reverse_geocoding_and_tracking_data(self):
        hints = AdDto.from_json(_page()).location.hints

        self.assertEqual("malopolskie", hints.province_code)
        self.assertEqual("powiat-krakow", hints.county_code)
        self.assertEqual(38, hints.city_id)
        self.assertEqual("Kraków", hints.city_name)
        self.assertEqual("pradnik-bialy", hints.district_code)
        self.assertEqual("Prądnik Biały", hints.district_name)

    def test_a_page_without_location_data_has_no_hints(self):
        page = _page(location={"coordinates": None, "address": None}, tracking={})

        self.assertIsNone(AdDto.from_json(page).location.hints)

    def test_a_non_numeric_city_id_is_ignored(self):
        hints = LocationHintsDto.from_json(_LOCATION, {**_TRACKING, "city_id": "abc"})

        self.assertIsNone(hints.city_id)
        self.assertEqual("krakow", hints.city_code)


class TestCompleteLocation(unittest.TestCase):

    def test_ids_resolve_to_existing_rows(self):
        ad = AdDto.from_json(_page())

        complete_location(ad, _index())

        address = ad.location.address
        self.assertEqual((6, 410, 38, 65), (address.province.id, address.county.id, address.city.id, address.district.id))
        self.assertEqual("ul. Henryka Pachońskiego", address.street.name)

    def test_a_shared_district_code_resolves_within_its_city(self):
        location = {**_LOCATION, "reverseGeocoding": {"locations": [
            {"id": "malopolskie/krakow/krakow/krakow", "locationLevel": "city_or_village", "name": "Kraków"},
            {"id": "malopolskie/krakow/krakow/krakow/zwierzyniec", "locationLevel": "district", "name": "Zwierzyniec"},
        ]}}
        ad = AdDto.from_json(_page(location=location))

        complete_location(ad, _index())

        self.assertEqual(71, ad.location.address.district.id)

    def test_an_existing_district_without_ads_is_reused_when_its_code_is_unique(self):
        index = LocationIndex.build(
            provinces=[], counties=[], city_ids=[38], districts=[(65, "pradnik-bialy")], district_usage=[],
        )
        ad = AdDto.from_json(_page())

        complete_location(ad, index)

        self.assertEqual(65, ad.location.address.district.id)

    def test_a_unique_district_already_used_by_another_city_is_not_borrowed(self):
        index = LocationIndex.build(
            provinces=[], counties=[], city_ids=[38], districts=[(65, "pradnik-bialy")],
            district_usage=[(991, "pradnik-bialy", 65, 4)],
        )
        ad = AdDto.from_json(_page())

        complete_location(ad, index)

        self.assertLess(ad.location.address.district.id, 0)

    def test_an_unknown_district_gets_a_stable_negative_id(self):
        location = {**_LOCATION, "reverseGeocoding": {"locations": [
            {"id": "malopolskie/krakow/krakow/krakow/nowa-dzielnica", "locationLevel": "district", "name": "Nowa"},
        ]}}
        first = AdDto.from_json(_page(location=location))
        second = AdDto.from_json(_page(location=location))
        index = _index()

        complete_location(first, index)
        complete_location(second, index)

        district_id = first.location.address.district.id
        self.assertLess(district_id, 0)
        self.assertEqual(district_id, second.location.address.district.id)
        self.assertEqual(
            synthetic_location_id("district", "malopolskie/krakow/krakow/krakow/nowa-dzielnica"), district_id
        )

    def test_values_from_the_old_address_format_win(self):
        ad = AdDto.from_json(_page())
        ad.location.address = replace(ad.location.address, city=CityDto(id=190, code="lublin", name="Lublin"))

        complete_location(ad, _index())

        self.assertEqual(190, ad.location.address.city.id)

    def test_an_unknown_city_id_from_tracking_is_kept(self):
        ad = AdDto.from_json(_page(tracking={**_TRACKING, "city_id": "777"}))

        complete_location(ad, _index())

        self.assertEqual(777, ad.location.address.city.id)
        self.assertEqual("Kraków", ad.location.address.city.name)


class TestAdFillLocation(unittest.TestCase):

    def _dto(self, address: AddressDto) -> AdDto:
        return AdDto(
            id=1, public_id="x", slug="x", url="https://www.otodom.pl/pl/oferta/x", title="t", description="",
            created_at=datetime(2026, 6, 1), modified_at=datetime(2026, 6, 1), status="active", market="SECONDARY",
            advertiser_type="private", price=PriceDto(value=1, currency="PLN", per_m2=1),
            location=LocationDto(coordinates=CoordinatesDto(50.0, 19.9), address=address),
            property=None, owner=None, features=[], images=[], characteristics=[],
        )

    def test_update_fills_a_missing_location(self):
        ad = Ad(id=1, city_id=None)
        dto = AdDto.from_json(_page())
        complete_location(dto, _index())

        ad.update(dto)

        self.assertEqual((6, 410, 38, 65), (ad.province_id, ad.county_id, ad.city_id, ad.district_id))

    def test_update_never_wipes_a_known_location(self):
        ad = Ad(id=1, province_id=6, county_id=410, city_id=38, district_id=65, street="ul. Stara")

        ad.update(self._dto(AddressDto(None, None, None, None, None, None)))

        self.assertEqual((6, 410, 38, 65, "ul. Stara"), (ad.province_id, ad.county_id, ad.city_id, ad.district_id, ad.street))


class TestRawPayload(unittest.TestCase):

    def test_only_the_ad_tracking_and_development_parts_are_kept(self):
        payload = AdDto.from_json(_page()).raw_payload

        self.assertEqual({"ad", "adTrackingData", "developmentData"}, set(payload))

    def test_a_stored_payload_can_be_parsed_again(self):
        payload = AdDto.from_json(_page()).raw_payload

        replayed = AdDto.from_json(as_page_json(decompress_payload(compress_payload(payload))))

        self.assertEqual(68512288, replayed.id)
        self.assertEqual(38, replayed.location.hints.city_id)


if __name__ == "__main__":
    unittest.main()
