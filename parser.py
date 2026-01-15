import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from scraper import Scraper


@dataclass
class Coordinates:
    latitude: float
    longitude: float


@dataclass
class District:
    id: str
    code: str
    name: str


@dataclass
class City:
    id: str
    code: str
    name: str


@dataclass
class County:
    id: str
    code: str
    name: str


@dataclass
class Province:
    id: str
    code: str
    name: str


@dataclass
class Address:
    street: Optional[str]
    district: Optional[District]
    city: Optional[City]
    county: Optional[County]
    province: Optional[Province]
    postal_code: Optional[str]


@dataclass
class Location:
    coordinates: Coordinates
    address: Address


@dataclass
class Price:
    value: int
    currency: str
    per_m2: int


@dataclass
class Area:
    value: float
    unit: str


@dataclass
class Rent:
    value: int
    currency: str


@dataclass
class BuildingProperties:
    year: Optional[int]
    type: Optional[str]
    material: Optional[str]
    windows: List[str]
    heating: Optional[str]
    number_of_floors: Optional[int]
    conveniences: List[str]
    security: List[str]


@dataclass
class FlatProperties:
    equipment: List[str]
    areas: List[str]
    floor: Optional[str]
    number_of_rooms: Optional[int]
    parking: List[str]


@dataclass
class Property:
    type: str
    condition: Optional[str]
    ownership: Optional[str]
    area: Area
    rent: Optional[Rent]
    flat_properties: FlatProperties
    building_properties: BuildingProperties


@dataclass
class Owner:
    id: int
    name: str
    type: str
    phones: List[str]


@dataclass
class Image:
    thumbnail: str
    small: str
    medium: str
    large: str


@dataclass
class Characteristic:
    key: str
    value: str
    localized_value: str
    currency: str


@dataclass
class Ad:
    id: int
    public_id: str
    slug: str
    url: str
    title: str
    description: str
    created_at: datetime
    modified_at: datetime
    status: str
    market: str
    advertiser_type: str
    price: Price
    location: Location
    property: Property
    owner: Owner
    features: List[str]
    images: List[Image]
    characteristics: List[Characteristic]

    def __str__(self):
        dictionary = dataclasses.asdict(self)
        dumps = json.dumps(dictionary, indent=4, sort_keys=True, default=str)
        return dumps.encode('utf-8').decode('unicode_escape')


class OtodomParser:

    def parse(self, data: dict) -> Ad:
        ad_data = data['props']['pageProps']['ad']
        return self._parse_ad(ad_data)

    def _parse_ad(self, ad: dict) -> Ad:
        return Ad(
            id=ad['id'],
            public_id=ad['publicId'],
            slug=ad['slug'],
            url=ad['url'],
            title=ad['title'],
            description=ad['description'],
            created_at=datetime.fromisoformat(ad['createdAt']),
            modified_at=datetime.fromisoformat(ad['modifiedAt']),
            status=ad['status'],
            market=ad['market'],
            advertiser_type=ad['advertiserType'],
            price=self._parse_price(ad),
            location=self._parse_location(ad['location']),
            property=self._parse_property(ad['property']),
            owner=self._parse_owner(ad['owner']),
            features=ad.get('features', []),
            images=self._parse_images(ad.get('images', [])),
            characteristics=self._parse_characteristics(ad.get('characteristics', []))
        )

    def _parse_location(self, loc: dict) -> Location:
        coords = loc.get('coordinates', {})
        addr = loc.get('address', {})

        return Location(
            coordinates=Coordinates(
                latitude=coords.get('latitude', 0),
                longitude=coords.get('longitude', 0)
            ),
            address=Address(
                street=addr.get('street'),
                district=self._parse_district(addr.get('district')),
                city=self._parse_city(addr.get('city')),
                county=self._parse_county(addr.get('county')),
                province=self._parse_province(addr.get('province')),
                postal_code=addr.get('postalCode')
            )
        )

    @staticmethod
    def _parse_price(ad: dict) -> Price:
        target = ad.get('target', {})
        return Price(
            value=target.get('Price', 0),
            currency='PLN',
            per_m2=target.get('Price_per_m', 0)
        )

    @staticmethod
    def _parse_district(data: Optional[dict]) -> Optional[District]:
        if not data:
            return None
        return District(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_city(data: Optional[dict]) -> Optional[City]:
        if not data:
            return None
        return City(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_county(data: Optional[dict]) -> Optional[County]:
        if not data:
            return None
        return County(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_province(data: Optional[dict]) -> Optional[Province]:
        if not data:
            return None
        return Province(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_property(prop: dict) -> Property:
        area_data = prop.get('area', {})
        rent_data = prop.get('rent')
        flat_props = prop.get('properties', {})
        building_props = prop.get('buildingProperties', {})

        return Property(
            type=prop.get('type', ''),
            condition=prop.get('condition'),
            ownership=prop.get('ownership'),
            area=Area(
                value=area_data.get('value', 0),
                unit=area_data.get('unit', 'M2')
            ),
            rent=Rent(
                value=rent_data.get('value', 0),
                currency=rent_data.get('currency', 'PLN')
            ) if rent_data else None,
            flat_properties=FlatProperties(
                equipment=flat_props.get('equipment', []),
                areas=flat_props.get('areas', []),
                floor=flat_props.get('floor'),
                number_of_rooms=flat_props.get('numberOfRooms'),
                parking=flat_props.get('parking', [])
            ),
            building_properties=BuildingProperties(
                year=building_props.get('year'),
                type=building_props.get('type'),
                material=building_props.get('material'),
                windows=building_props.get('windows', []),
                heating=building_props.get('heating'),
                number_of_floors=building_props.get('numberOfFloors'),
                conveniences=building_props.get('conveniences', []),
                security=building_props.get('security', [])
            )
        )

    @staticmethod
    def _parse_owner(owner: dict) -> Owner:
        return Owner(
            id=owner['id'],
            name=owner['name'],
            type=owner['type'],
            phones=owner.get('phones', [])
        )

    @staticmethod
    def _parse_images(images: List[dict]) -> List[Image]:
        return [
            Image(
                thumbnail=img['thumbnail'],
                small=img['small'],
                medium=img['medium'],
                large=img['large']
            )
            for img in images
        ]

    @staticmethod
    def _parse_characteristics(chars: List[dict]) -> List[Characteristic]:
        return [
            Characteristic(
                key=c['key'],
                value=c['value'],
                localized_value=c['localizedValue'],
                currency=c.get('currency', '')
            )
            for c in chars
        ]


if __name__ == '__main__':
    test_url = "https://www.otodom.pl/pl/oferta/rezerwacja-mieszkanie-wysoki-standard-blisko-uczelni-medycznej-ID4znz8"
    scraper = Scraper()
    parser = OtodomParser()
    scrape = scraper.scrape(test_url)
    _ad = parser.parse(scrape)
    # print(_ad.title)
    # print(_ad.price.value)
    # print(_ad.location.address.city.name)
    # print(_ad.characteristics)
    # print(_ad.features)
    print(_ad)
