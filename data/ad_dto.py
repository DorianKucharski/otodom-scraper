import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict
from functools import cached_property
import re
from typing import Optional, Type, TypeVar

T = TypeVar("T")


def parse_datetime(value: str) -> datetime:
    # Python 3.10's datetime.fromisoformat does not accept a trailing "Z".
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_float(value: str) -> Optional[float]:
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    value = value.replace(" ", "")
    value = value.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


class CharacteristicKey(str, Enum):
    BUILD_YEAR = "build_year"
    BUILDING_FLOORS_NUM = "building_floors_num"
    BUILDING_MATERIAL = "building_material"
    BUILDING_OWNERSHIP = "building_ownership"
    BUILDING_TYPE = "building_type"
    CONSTRUCTION_STATUS = "construction_status"
    DEPOSIT = "deposit"
    ENERGY_CERTIFICATE = "energy_certificate"
    FLAT_NUMBER = "flat_number"
    FLAT_PROJECTION = "flat_projection"
    FLOOR_NO = "floor_no"
    FLOORS_NUM = "floors_num"
    FREE_FROM = "free_from"
    GARRET_TYPE = "garret_type"
    HEATING = "heating"
    LOCATION = "location"
    M = "m"
    MARKET = "market"
    PRICE = "price"
    PRICE_PER_M = "price_per_m"
    REMOTE_SERVICES = "remote_services"
    RENT = "rent"
    ROOF_TYPE = "roof_type"
    ROOFING = "roofing"
    ROOMS_NUM = "rooms_num"
    TERRAIN_AREA = "terrain_area"
    WINDOWS_TYPE = "windows_type"


@dataclass
class CoordinatesDto:
    latitude: float
    longitude: float

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['CoordinatesDto']:
        if not data:
            return None
        return cls(
            latitude=data.get('latitude', 0),
            longitude=data.get('longitude', 0)
        )


@dataclass
class DistrictDto:
    id: int
    code: str
    name: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['DistrictDto']:
        if not data:
            return None
        return cls(id=int(data['id']), code=data['code'], name=data['name'])


@dataclass
class CityDto:
    id: int
    code: str
    name: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['CityDto']:
        if not data:
            return None
        return cls(id=int(data['id']), code=data['code'], name=data['name'])


@dataclass
class CountyDto:
    id: int
    code: str
    name: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['CountyDto']:
        if not data:
            return None
        return cls(id=(data['id']), code=data['code'], name=data['name'])


@dataclass
class ProvinceDto:
    id: int
    code: str
    name: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['ProvinceDto']:
        if not data:
            return None
        return cls(id=(data['id']), code=data['code'], name=data['name'])


@dataclass
class StreetDto:
    id: Optional[int]  # Not sure if its set
    code: Optional[str]  # Not sure if its set
    name: str
    number: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['StreetDto']:
        if not data:
            return None
        return cls(
            id=int(data['id']) if data['id'] else None,
            code=data['code'],
            name=data['name'],
            number=data['number']
        )


@dataclass
class AddressDto:
    street: Optional[StreetDto]
    district: Optional[DistrictDto]
    city: Optional[CityDto]
    county: Optional[CountyDto]
    province: Optional[ProvinceDto]
    postal_code: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['AddressDto']:
        if not data:
            return None

        return cls(
            street=StreetDto.from_json(data.get('street')),
            district=DistrictDto.from_json(data.get('district')),
            city=CityDto.from_json(data.get('city')),
            county=CountyDto.from_json(data.get('county')),
            province=ProvinceDto.from_json(data.get('province')),
            postal_code=data.get('postalCode')
        )


@dataclass
class LocationDto:
    coordinates: Optional[CoordinatesDto]
    address: Optional[AddressDto]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['LocationDto']:
        if not data:
            return None
        return cls(
            coordinates=CoordinatesDto.from_json(data.get('coordinates')),
            address=AddressDto.from_json(data.get('address'))
        )


@dataclass
class PriceDto:
    value: int
    currency: str
    per_m2: int

    @classmethod
    def from_json(cls, ad: dict) -> 'PriceDto':
        target = ad.get('target', {})
        return cls(
            value=target.get('Price', 0),
            currency='PLN',
            per_m2=target.get('Price_per_m', 0)
        )


@dataclass
class AreaDto:
    value: float
    unit: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['AreaDto']:
        if not data:
            return None
        return cls(
            value=data.get('value', 0),
            unit=data.get('unit', 'M2')
        )


@dataclass
class RentDto:
    value: int
    currency: str

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['RentDto']:
        if not data:
            return None
        return cls(
            value=data.get('value', 0),
            currency=data.get('currency', 'PLN')
        )


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

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['BuildingPropertiesDto']:
        if not data:
            return None
        return cls(
            year=data.get('year'),
            type=data.get('type'),
            material=data.get('material'),
            windows=data.get('windows', []),
            heating=data.get('heating'),
            number_of_floors=data.get('numberOfFloors'),
            conveniences=data.get('conveniences', []),
            security=data.get('security', [])
        )


@dataclass
class FlatPropertiesDto:
    equipment: List[str]
    areas: List[str]
    floor: Optional[str]
    number_of_rooms: Optional[int]
    parking: List[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['FlatPropertiesDto']:
        if not data:
            return None
        return cls(
            equipment=data.get('equipment', []),
            areas=data.get('areas', []),
            floor=data.get('floor'),
            number_of_rooms=data.get('numberOfRooms'),
            parking=data.get('parking', [])
        )


@dataclass
class PropertyDto:
    type: str
    condition: Optional[str]
    ownership: Optional[str]
    area: Optional[AreaDto]
    rent: Optional[RentDto]
    flat_properties: Optional[FlatPropertiesDto]
    building_properties: Optional[BuildingPropertiesDto]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['PropertyDto']:
        if not data:
            return None
        return cls(
            type=data.get('type', ''),
            condition=data.get('condition'),
            ownership=data.get('ownership'),
            area=AreaDto.from_json(data.get('area')),
            rent=RentDto.from_json(data.get('rent')),
            flat_properties=FlatPropertiesDto.from_json(data.get('properties')),
            building_properties=BuildingPropertiesDto.from_json(data.get('buildingProperties'))
        )


@dataclass
class OwnerDto:
    id: int
    name: str
    type: str
    phones: List[str]

    @classmethod
    def from_json(cls, data: dict) -> 'OwnerDto':
        return cls(
            id=int(data['id']),
            name=data['name'],
            type=data['type'],
            phones=data.get('phones', [])
        )


@dataclass
class ImageDto:
    position: int
    thumbnail: str
    small: str
    medium: str
    large: str

    @classmethod
    def from_json(cls, data: dict, position: int) -> 'ImageDto':
        return cls(
            position=position,
            thumbnail=data['thumbnail'],
            small=data['small'],
            medium=data['medium'],
            large=data['large']
        )

    @classmethod
    def from_json_list(cls, data: Optional[List[dict]]) -> List['ImageDto']:
        if not data:
            return []
        return [cls.from_json(img, i) for i, img in enumerate(data)]


@dataclass
class CharacteristicDto:
    key: str
    value: str
    localized_value: str
    currency: str

    def get_value(self, cast_type: Type[T] = str) -> Optional[T]:
        return self.__cast_value(self.value, cast_type)

    def get_localized_value(self, cast_type: Type[T] = str) -> Optional[T]:
        return self.__cast_value(self.localized_value, cast_type)

    @staticmethod
    def __cast_value(str_value: str, cast_type: Type[T] = str) -> Optional[T]:
        if cast_type is float:
            return parse_float(str_value)

        try:
            return cast_type(str_value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_json(cls, data: dict) -> 'CharacteristicDto':
        return cls(
            key=data['key'],
            value=data['value'],
            localized_value=data['localizedValue'],
            currency=data.get('currency', '')
        )

    @classmethod
    def from_json_list(cls, data: Optional[List[dict]]) -> List['CharacteristicDto']:
        if not data:
            return []
        return [cls.from_json(c) for c in data]


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
    location: Optional[LocationDto]
    property: Optional[PropertyDto]
    owner: OwnerDto
    features: List[str]
    images: List[ImageDto]
    characteristics: List[CharacteristicDto]

    @cached_property
    def characteristic_by_key(self) -> Dict[str, CharacteristicDto]:
        return {c.key: c for c in self.characteristics}

    def get_characteristic(self, key: CharacteristicKey) -> Optional[CharacteristicDto]:
        return self.characteristic_by_key.get(key.value)

    def __str__(self):
        dictionary = dataclasses.asdict(self)
        dumps = json.dumps(dictionary, indent=4, sort_keys=True, default=str)
        return dumps.encode('utf-8').decode('unicode_escape')

    @classmethod
    def from_json(cls, data: dict) -> Optional['AdDto']:
        ad = data.get('props', {}).get('pageProps', {}).get('ad')
        if ad is None:
            return None
        return cls(
            id=ad['id'],
            public_id=ad['publicId'],
            slug=ad['slug'],
            url=ad['url'],
            title=ad['title'],
            description=ad['description'],
            created_at=parse_datetime(ad['createdAt']),
            modified_at=parse_datetime(ad['modifiedAt']),
            status=ad['status'],
            market=ad['market'],
            advertiser_type=ad['advertiserType'],
            price=PriceDto.from_json(ad),
            location=LocationDto.from_json(ad.get('location')),
            property=PropertyDto.from_json(ad.get('property')),
            owner=OwnerDto.from_json(ad['owner']),
            features=ad.get('features', []),
            images=ImageDto.from_json_list(ad.get('images')),
            characteristics=CharacteristicDto.from_json_list(ad.get('characteristics'))
        )
