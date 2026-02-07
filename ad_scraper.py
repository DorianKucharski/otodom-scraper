import dataclasses
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import cloudscraper
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CoordinatesDto:
    latitude: float
    longitude: float


@dataclass
class DistrictDto:
    id: str
    code: str
    name: str


@dataclass
class CityDto:
    id: str
    code: str
    name: str


@dataclass
class CountyDto:
    id: str
    code: str
    name: str


@dataclass
class ProvinceDto:
    id: str
    code: str
    name: str


@dataclass
class AddressDto:
    street: Optional[str]
    district: Optional[DistrictDto]
    city: Optional[CityDto]
    county: Optional[CountyDto]
    province: Optional[ProvinceDto]
    postal_code: Optional[str]


@dataclass
class LocationDto:
    coordinates: CoordinatesDto
    address: AddressDto


@dataclass
class PriceDto:
    value: int
    currency: str
    per_m2: int


@dataclass
class AreaDto:
    value: float
    unit: str


@dataclass
class RentDto:
    value: int
    currency: str


@dataclass
class BuildingPropertiesDto:
    year: Optional[int]
    type: Optional[str]
    material: Optional[str]
    windows: List[str]
    heating: Optional[str]
    number_of_floors: Optional[int]
    conveniences: List[str]
    security: List[str]


@dataclass
class FlatPropertiesDto:
    equipment: List[str]
    areas: List[str]
    floor: Optional[str]
    number_of_rooms: Optional[int]
    parking: List[str]


@dataclass
class PropertyDto:
    type: str
    condition: Optional[str]
    ownership: Optional[str]
    area: AreaDto
    rent: Optional[RentDto]
    flat_properties: FlatPropertiesDto
    building_properties: BuildingPropertiesDto


@dataclass
class OwnerDto:
    id: int
    name: str
    type: str
    phones: List[str]


@dataclass
class ImageDto:
    thumbnail: str
    small: str
    medium: str
    large: str


@dataclass
class CharacteristicDto:
    key: str
    value: str
    localized_value: str
    currency: str


@dataclass
class AdDto:
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
    price: PriceDto
    location: LocationDto
    property: PropertyDto
    owner: OwnerDto
    features: List[str]
    images: List[ImageDto]
    characteristics: List[CharacteristicDto]

    def __str__(self):
        dictionary = dataclasses.asdict(self)
        dumps = json.dumps(dictionary, indent=4, sort_keys=True, default=str)
        return dumps.encode('utf-8').decode('unicode_escape')


class AdParser:

    def parse(self, data: dict) -> AdDto:
        ad_data = data['props']['pageProps']['ad']
        return self._parse_ad(ad_data)

    def _parse_ad(self, ad: dict) -> AdDto:
        return AdDto(
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

    def _parse_location(self, loc: dict) -> LocationDto:
        coords = loc.get('coordinates', {})
        addr = loc.get('address', {})

        return LocationDto(
            coordinates=CoordinatesDto(
                latitude=coords.get('latitude', 0),
                longitude=coords.get('longitude', 0)
            ),
            address=AddressDto(
                street=addr.get('street'),
                district=self._parse_district(addr.get('district')),
                city=self._parse_city(addr.get('city')),
                county=self._parse_county(addr.get('county')),
                province=self._parse_province(addr.get('province')),
                postal_code=addr.get('postalCode')
            )
        )

    @staticmethod
    def _parse_price(ad: dict) -> PriceDto:
        target = ad.get('target', {})
        return PriceDto(
            value=target.get('Price', 0),
            currency='PLN',
            per_m2=target.get('Price_per_m', 0)
        )

    @staticmethod
    def _parse_district(data: Optional[dict]) -> Optional[DistrictDto]:
        if not data:
            return None
        return DistrictDto(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_city(data: Optional[dict]) -> Optional[CityDto]:
        if not data:
            return None
        return CityDto(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_county(data: Optional[dict]) -> Optional[CountyDto]:
        if not data:
            return None
        return CountyDto(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_province(data: Optional[dict]) -> Optional[ProvinceDto]:
        if not data:
            return None
        return ProvinceDto(id=data['id'], code=data['code'], name=data['name'])

    @staticmethod
    def _parse_property(prop: dict) -> PropertyDto:
        area_data = prop.get('area', {})
        rent_data = prop.get('rent')
        flat_props = prop.get('properties', {})
        building_props = prop.get('buildingProperties', {})

        return PropertyDto(
            type=prop.get('type', ''),
            condition=prop.get('condition'),
            ownership=prop.get('ownership'),
            area=AreaDto(
                value=area_data.get('value', 0),
                unit=area_data.get('unit', 'M2')
            ),
            rent=RentDto(
                value=rent_data.get('value', 0),
                currency=rent_data.get('currency', 'PLN')
            ) if rent_data else None,
            flat_properties=FlatPropertiesDto(
                equipment=flat_props.get('equipment', []),
                areas=flat_props.get('areas', []),
                floor=flat_props.get('floor'),
                number_of_rooms=flat_props.get('numberOfRooms'),
                parking=flat_props.get('parking', [])
            ),
            building_properties=BuildingPropertiesDto(
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
    def _parse_owner(owner: dict) -> OwnerDto:
        return OwnerDto(
            id=owner['id'],
            name=owner['name'],
            type=owner['type'],
            phones=owner.get('phones', [])
        )

    @staticmethod
    def _parse_images(images: List[dict]) -> List[ImageDto]:
        return [
            ImageDto(
                thumbnail=img['thumbnail'],
                small=img['small'],
                medium=img['medium'],
                large=img['large']
            )
            for img in images
        ]

    @staticmethod
    def _parse_characteristics(chars: List[dict]) -> List[CharacteristicDto]:
        return [
            CharacteristicDto(
                key=c['key'],
                value=c['value'],
                localized_value=c['localizedValue'],
                currency=c.get('currency', '')
            )
            for c in chars
        ]


class AdScraper:
    def __init__(self):
        self.__scraper = cloudscraper.create_scraper()
        self.__parser = AdParser()

    def scrape(self, url: str) -> AdDto:
        response = self.__scraper.get(url)
        if response.status_code != 200:
            raise Exception(f"Error getting page: {response.status_code} - {url}")
        text = response.text
        soup = BeautifulSoup(text, 'html.parser')
        ad_json_text = soup.find(name='script', attrs={'type': 'application/json'})
        ad_json = json.loads(ad_json_text.text)
        logger.info("Successfully scraped page")
        ad_dataclass = self.__parser.parse(ad_json)
        logger.info(f"Parsed ad: {ad_dataclass.title}")
        return ad_dataclass


if __name__ == "__main__":
    _scraper = AdScraper()
    _url = "https://www.otodom.pl/pl/oferta/mieszkanie-lublin-45-4m2-2-pietro-2-pok-ID4zYrx"
    _scrape = _scraper.scrape(_url)
    print(_scrape)
