from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlencode

BASE_URL = "https://www.otodom.pl/pl/wyniki"


class OfferType(Enum):
    SALE = "sprzedaz"
    RENT = "wynajem"


class ObjectType(Enum):
    APARTMENT = "mieszkanie"
    STUDIO = "kawalerka"
    HOUSE = "dom"
    INVESTMENT = "inwestycja"  # offerType: SALE
    ROOM = "pokoj"  # offerType: RENT
    LAND = "dzialka"
    COMMERCIAL = "lokal"
    WAREHOUSE = "haleimagazyny"
    GARAGE = "garaz"


class RoomsNumber(Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SIX_OR_MORE = 7

    @classmethod
    def from_int(cls, value: int) -> 'RoomsNumber':
        for room in cls:
            if room.value == value:
                return room
        return cls.SIX_OR_MORE


class SortBy(Enum):
    DEFAULT = "DEFAULT"
    DATE = "LATEST"
    PRICE = "PRICE"
    AREA = "AREA"


class SortDirection(Enum):
    ASC = "ASC"
    DESC = "DESC"


class PageLimit(Enum):
    LIMIT_24 = 24
    LIMIT_36 = 36
    LIMIT_48 = 48
    LIMIT_72 = 72


@dataclass
class Location:
    voivodeship: str
    city: Optional[str] = None
    district: Optional[str] = None
    distance_radius: Optional[int] = None

    def __init__(
            self,
            voivodeship: str,
            city: Optional[str] = None,
            district: Optional[str] = None,
            distance_radius: Optional[int] = None,
    ):
        if not voivodeship:
            raise Exception("Voivodeship is required")
        if city and not voivodeship:
            raise Exception("Voivodeship is required when city is provided")
        if district and not city:
            raise Exception("City is required when district is provided")

        self.voivodeship = voivodeship
        self.city = city
        self.district = district
        self.distance_radius = distance_radius


@dataclass
class SearchUrl:
    offer_type: OfferType
    object_type: ObjectType

    sort_by: SortBy
    sort_direction: SortDirection
    page_limit: PageLimit
    page_number: int

    location: Optional[Location] = None

    price_from: Optional[int] = None
    price_to: Optional[int] = None

    def __init__(
            self,
            offer_type: OfferType,
            object_type: ObjectType,

            sort_by: Optional[SortBy] = SortBy.DEFAULT,
            sort_direction: Optional[SortDirection] = SortDirection.DESC,
            page_limit: Optional[PageLimit] = PageLimit.LIMIT_36,
            page_number: Optional[int] = 1,

            location: Optional[Location] = None,

            price_from: Optional[int] = None,
            price_to: Optional[int] = None,

    ):
        if not offer_type or not object_type:
            raise Exception("Offer type and object type are required")
        if object_type == ObjectType.INVESTMENT and offer_type == OfferType.RENT:
            raise Exception("Investment offer type is not supported for rent objects")
        if object_type == ObjectType.ROOM and offer_type == OfferType.SALE:
            raise Exception("Room offer type is not supported for sale objects")

        self.offer_type = offer_type
        self.object_type = object_type

        self.sort_by = sort_by
        self.sort_direction = sort_direction
        self.page_limit = page_limit
        self.page_number = page_number

        self.location = location

        self.price_from = price_from
        self.price_to = price_to

    def build(self) -> str:
        path = f"{BASE_URL}/{self.offer_type.value}/{self.object_type.value}"

        if self.location:
            if self.location.voivodeship:
                path += f"/{self.location.voivodeship}"
            if self.location.city:
                path += f"/{self.location.city}/{self.location.city}/{self.location.city}"
            if self.location.district:
                path += f"/{self.location.district}"
        else:
            path += "/cala-polska"

        params = {
            'page': self.page_number,
            'limit': self.page_limit.value,
            'by': self.sort_by.value,
            'direction': self.sort_direction.value,
        }
        if self.price_from:
            params['priceMin'] = self.price_from
        if self.price_to:
            params['priceMax'] = self.price_to
        if self.location.distance_radius:
            params['distanceRadius'] = self.location.distance_radius

        return path + "?" + urlencode(params)

    def next_page(self):
        self.page_number += 1


@dataclass
class ApartmentSearchUrl(SearchUrl):
    area_from: Optional[int] = None
    area_to: Optional[int] = None
    rooms_from: Optional[int] = None
    rooms_to: Optional[int] = None


@dataclass
class StudioSearchUrl(SearchUrl):
    area_from: Optional[int] = None
    area_to: Optional[int] = None


@dataclass
class HouseSearchUrl(SearchUrl):
    area_from: Optional[int] = None
    area_to: Optional[int] = None
    rooms_from: Optional[int] = None
    rooms_to: Optional[int] = None


@dataclass
class InvestmentSearchUrl(SearchUrl):
    area_from: Optional[int] = None
    area_to: Optional[int] = None
    rooms_from: Optional[int] = None
    rooms_to: Optional[int] = None


@dataclass
class RoomSearchUrl(SearchUrl):
    availability: Optional[str] = None
    amount_of_people_in_room: Optional[int] = None


if __name__ == "__main__":
    url = SearchUrl(
        offer_type=OfferType.SALE,
        object_type=ObjectType.HOUSE,
        location=Location(
            voivodeship="mazowieckie",
            city="warszawa",
        ),
        price_to=1000000,

    )

    print(url.build())
    url.next_page()
    print(url.build())
