from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


@dataclass
class MoneyDto:
    value: Optional[float]
    currency: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['MoneyDto']:
        if not data:
            return None
        return cls(
            value=data.get("value"),
            currency=data.get("currency"),
        )


@dataclass
class SearchImageDto:
    medium: Optional[str]
    large: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['SearchImageDto']:
        if not data:
            return None
        return cls(
            medium=data.get("medium"),
            large=data.get("large"),
        )

    @classmethod
    def from_json_list(cls, data: Optional[list]) -> List['SearchImageDto']:
        if not data:
            return []
        return [cls.from_json(img) for img in data if img]


@dataclass
class AgencyDto:
    id: Optional[int]
    name: Optional[str]
    slug: Optional[str]
    image_url: Optional[str]
    type: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['AgencyDto']:
        if not data:
            return None
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            slug=data.get("slug"),
            image_url=data.get("imageUrl"),
            type=data.get("type"),
        )


@dataclass
class StreetDto:
    name: Optional[str]
    number: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['StreetDto']:
        if not data:
            return None
        return cls(
            name=data.get("name"),
            number=data.get("number"),
        )


@dataclass
class CityNameDto:
    name: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['CityNameDto']:
        if not data:
            return None
        return cls(name=data.get("name"))


@dataclass
class ProvinceNameDto:
    name: Optional[str]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['ProvinceNameDto']:
        if not data:
            return None
        return cls(name=data.get("name"))


@dataclass
class AddressDto:
    street: Optional[StreetDto]
    city: Optional[CityNameDto]
    province: Optional[ProvinceNameDto]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['AddressDto']:
        if not data:
            return None
        return cls(
            street=StreetDto.from_json(data.get("street")),
            city=CityNameDto.from_json(data.get("city")),
            province=ProvinceNameDto.from_json(data.get("province")),
        )


@dataclass
class SearchAdLocationDto:
    address: Optional[AddressDto]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['SearchAdLocationDto']:
        if not data:
            return None
        return cls(
            address=AddressDto.from_json(data.get("address"))
        )


@dataclass
class InvestmentUnitsAreaDto:
    from_m2: Optional[float]
    to_m2: Optional[float]

    @classmethod
    def from_json(cls, data: Optional[dict]) -> Optional['InvestmentUnitsAreaDto']:
        if not data:
            return None
        return cls(
            from_m2=data.get("from"),
            to_m2=data.get("to"),
        )


@dataclass
class SearchAdDto:
    id: int
    url: str

    title: Optional[str]
    slug: Optional[str]
    estate: Optional[str]
    transaction: Optional[str]

    location: Optional[SearchAdLocationDto]

    images: List[SearchImageDto]
    total_possible_images: Optional[int]

    is_private_owner: Optional[bool]
    is_promoted: Optional[bool]
    is_exclusive_offer: Optional[bool]

    agency: Optional[AgencyDto]

    short_description: Optional[str]
    row_index: Optional[int]

    created_at_first: Optional[datetime]
    pushed_up_at: Optional[datetime]

    rooms_number_raw: Optional[str]
    rooms_number: Optional[int]

    floor_number_raw: Optional[str]
    floor_number: Optional[int]

    area_in_square_meters: Optional[float]

    total_price: Optional[MoneyDto]
    rent_price: Optional[MoneyDto]
    price_per_square_meter: Optional[MoneyDto]
    price_from_per_square_meter: Optional[MoneyDto]

    investment_state: Optional[str]
    investment_units_area_in_square_meters: Optional[InvestmentUnitsAreaDto]
    investment_units_number: Optional[int]

    @classmethod
    def from_json(cls, ad: dict) -> 'SearchAdDto':
        estate = ad.get("estate")
        rooms_raw = ad.get("roomsNumber")
        floor_raw = ad.get("floorNumber")
        investment_units_area = ad.get("investmentUnitsAreaInSquareMeters")

        return cls(
            id=int(ad["id"]),
            url=cls._build_absolute_url(ad.get("href")),

            title=ad.get("title"),
            slug=ad.get("slug"),
            estate=estate,
            transaction=ad.get("transaction"),

            location=SearchAdLocationDto.from_json(ad.get("location")),

            images=SearchImageDto.from_json_list(ad.get("images")),
            total_possible_images=ad.get("totalPossibleImages"),

            is_private_owner=ad.get("isPrivateOwner"),
            is_promoted=ad.get("isPromoted"),
            is_exclusive_offer=ad.get("isExclusiveOffer"),

            agency=AgencyDto.from_json(ad.get("agency")),

            short_description=ad.get("shortDescription"),
            row_index=ad.get("rowIndex"),

            created_at_first=cls._parse_datetime(ad.get("createdAtFirst")),
            pushed_up_at=cls._parse_datetime(ad.get("pushedUpAt")),

            rooms_number_raw=rooms_raw,
            rooms_number=cls._map_rooms_number(rooms_raw),

            floor_number_raw=floor_raw,
            floor_number=cls._map_floor_number(floor_raw),

            area_in_square_meters=ad.get("areaInSquareMeters"),

            total_price=MoneyDto.from_json(ad.get("totalPrice")),
            rent_price=MoneyDto.from_json(ad.get("rentPrice")),
            price_per_square_meter=MoneyDto.from_json(ad.get("pricePerSquareMeter")),
            price_from_per_square_meter=MoneyDto.from_json(ad.get("priceFromPerSquareMeter")),

            investment_state=ad.get("investmentState") if estate == "INVESTMENT" else None,
            investment_units_area_in_square_meters=InvestmentUnitsAreaDto.from_json(investment_units_area)
            if investment_units_area and estate == "INVESTMENT" else None,
            investment_units_number=ad.get("investmentUnitsNumber") if estate == "INVESTMENT" else None,
        )

    @staticmethod
    def _build_absolute_url(href: str) -> str:
        if not href:
            return ""
        slug = href.split("/")[-1]
        return "https://www.otodom.pl/pl/oferta/" + slug

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            v = value.replace("Z", "+00:00")
            return datetime.fromisoformat(v)
        except ValueError:
            return None

    @staticmethod
    def _map_rooms_number(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        mapping = {
            "ONE": 1, "TWO": 2, "THREE": 3,
            "FOUR": 4, "FIVE": 5, "SIX": 6,
        }
        return mapping.get(value)

    @staticmethod
    def _map_floor_number(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        mapping = {
            "GROUND": 0, "FIRST": 1, "SECOND": 2, "THIRD": 3,
            "FOURTH": 4, "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7,
            "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
        }
        if value in mapping:
            return mapping[value]
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

@dataclass
class SearchResultDto:
    current_page: int
    items_per_page: int
    total_items: int
    total_pages: int
    items: List[SearchAdDto]

    @staticmethod
    def from_json(data: dict) -> 'SearchResultDto':
        search_ads = data['props']['pageProps']['data']['searchAds']
        pagination = search_ads['pagination']
        items = search_ads['items']
        return SearchResultDto(
            current_page=int(pagination['currentPage']),
            items_per_page=int(pagination['itemsPerPage']),
            total_items=int(pagination['totalItems']),
            total_pages=int(pagination['totalPages']),
            items=[SearchAdDto.from_json(item) for item in items]
        )
