import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

import cloudscraper
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =========================
# DTOs for searchAds.items
# =========================

@dataclass
class MoneyDto:
    value: Optional[float]
    currency: Optional[str]


@dataclass
class SearchImageDto:
    medium: Optional[str]
    large: Optional[str]


@dataclass


class AgencyDto:
    id: Optional[int]
    name: Optional[str]
    slug: Optional[str]
    image_url: Optional[str]
    type: Optional[str]


@dataclass
class StreetDto:
    name: Optional[str]
    number: Optional[str]


@dataclass
class CityNameDto:
    name: Optional[str]


@dataclass
class ProvinceNameDto:
    name: Optional[str]


@dataclass
class AddressDto:
    street: Optional[StreetDto]
    city: Optional[CityNameDto]
    province: Optional[ProvinceNameDto]


@dataclass
class SearchAdLocationDto:
    address: Optional[AddressDto]


@dataclass
class InvestmentUnitsAreaDto:
    from_m2: Optional[float]
    to_m2: Optional[float]


@dataclass
class SearchAdDto:
    # Common (for both FLAT and INVESTMENT)
    id: int
    url: str

    title: Optional[str]
    slug: Optional[str]
    estate: Optional[str]         # e.g. "FLAT", "INVESTMENT"
    transaction: Optional[str]    # e.g. "RENT", "SELL"

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

    # Normalized fields (handy for DB/filtering); may be None for INVESTMENT etc.
    rooms_number_raw: Optional[str]
    rooms_number: Optional[int]

    floor_number_raw: Optional[str]
    floor_number: Optional[int]

    area_in_square_meters: Optional[float]

    # Price-ish fields
    total_price: Optional[MoneyDto]
    rent_price: Optional[MoneyDto]
    price_per_square_meter: Optional[MoneyDto]
    price_from_per_square_meter: Optional[MoneyDto]

    # Investment-specific extras (only when estate == "INVESTMENT")
    investment_state: Optional[str]
    investment_units_area_in_square_meters: Optional[InvestmentUnitsAreaDto]
    investment_units_number: Optional[int]


class AdSearcherParser:
    def parse(self, data: dict) -> list[SearchAdDto]:
        items = data['props']['pageProps']['data']['searchAds']['items']
        return [self._parse_search_ad(item) for item in items]

    def _parse_search_ad(self, ad: dict) -> SearchAdDto:
        href = ad.get("href") or ""
        url = self._build_absolute_url(href)

        rooms_raw = ad.get("roomsNumber")
        floor_raw = ad.get("floorNumber")

        estate = ad.get("estate")
        investment_units_area = ad.get("investmentUnitsAreaInSquareMeters")

        return SearchAdDto(
            id=int(ad["id"]),
            url=url,

            title=ad.get("title"),
            slug=ad.get("slug"),
            estate=estate,
            transaction=ad.get("transaction"),

            location=self._parse_location(ad.get("location")),

            images=self._parse_images(ad.get("images", [])),
            total_possible_images=ad.get("totalPossibleImages"),

            is_private_owner=ad.get("isPrivateOwner"),
            is_promoted=ad.get("isPromoted"),
            is_exclusive_offer=ad.get("isExclusiveOffer"),

            agency=self._parse_agency(ad.get("agency")),

            short_description=ad.get("shortDescription"),
            row_index=ad.get("rowIndex"),

            created_at_first=self._parse_dt_iso(ad.get("createdAtFirst")),
            pushed_up_at=self._parse_dt_iso(ad.get("pushedUpAt")),

            rooms_number_raw=rooms_raw,
            rooms_number=self._map_rooms_number(rooms_raw),

            floor_number_raw=floor_raw,
            floor_number=self._map_floor_number(floor_raw),

            area_in_square_meters=ad.get("areaInSquareMeters"),

            total_price=self._parse_money(ad.get("totalPrice")),
            rent_price=self._parse_money(ad.get("rentPrice")),
            price_per_square_meter=self._parse_money(ad.get("pricePerSquareMeter")),
            price_from_per_square_meter=self._parse_money(ad.get("priceFromPerSquareMeter")),

            investment_state=ad.get("investmentState") if estate == "INVESTMENT" else None,
            investment_units_area_in_square_meters=self._parse_investment_units_area(investment_units_area)
            if investment_units_area and estate == "INVESTMENT" else None,
            investment_units_number=ad.get("investmentUnitsNumber") if estate == "INVESTMENT" else None,
        )

    # -------------------------
    # Mapping / Normalization
    # -------------------------

    @staticmethod
    def _map_rooms_number(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        mapping = {
            "ONE": 1,
            "TWO": 2,
            "THREE": 3,
            "FOUR": 4,
            "FIVE": 5,
            "SIX": 6,
        }
        return mapping.get(value)

    @staticmethod
    def _map_floor_number(value: Optional[str]) -> Optional[int]:
        """
        Note: for some listings floors might be strings like "GROUND", "FIRST", etc.
        If it ever comes as numeric string, we try to parse it too.
        """
        if not value:
            return None
        mapping = {
            "GROUND": 0,
            "FIRST": 1,
            "SECOND": 2,
            "THIRD": 3,
            "FOURTH": 4,
            "FIFTH": 5,
            "SIXTH": 6,
            "SEVENTH": 7,
            "EIGHTH": 8,
            "NINTH": 9,
            "TENTH": 10,
        }
        if value in mapping:
            return mapping[value]
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # -------------------------
    # Helpers
    # -------------------------

    @staticmethod
    def _build_absolute_url(href: str) -> str:
        if not href:
            return ""
        cleaned = href.replace("[lang]", "pl")
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        if not cleaned.startswith("/"):
            cleaned = "/" + cleaned
        return "https://www.otodom.pl" + cleaned

    @staticmethod
    def _parse_money(data: Optional[dict]) -> Optional[MoneyDto]:
        if not data:
            return None
        return MoneyDto(
            value=data.get("value"),
            currency=data.get("currency"),
        )

    @staticmethod
    def _parse_images(images: list[dict]) -> List[SearchImageDto]:
        out: List[SearchImageDto] = []
        for img in images or []:
            out.append(SearchImageDto(
                medium=img.get("medium"),
                large=img.get("large"),
            ))
        return out

    @staticmethod
    def _parse_agency(data: Optional[dict]) -> Optional[AgencyDto]:
        if not data:
            return None
        return AgencyDto(
            id=data.get("id"),
            name=data.get("name"),
            slug=data.get("slug"),
            image_url=data.get("imageUrl"),
            type=data.get("type"),
        )

    @classmethod
    def _parse_location(cls, data: Optional[dict]) -> Optional[SearchAdLocationDto]:
        if not data:
            return None
        addr = data.get("address") or {}
        return SearchAdLocationDto(
            address=cls._parse_address(addr) if addr else None
        )

    @staticmethod
    def _parse_address(addr: Optional[dict]) -> Optional[AddressDto]:
        if not addr:
            return None

        street = addr.get("street")
        city = addr.get("city")
        province = addr.get("province")

        return AddressDto(
            street=StreetDto(
                name=(street or {}).get("name"),
                number=(street or {}).get("number"),
            ) if street else None,
            city=CityNameDto(name=(city or {}).get("name")) if city else None,
            province=ProvinceNameDto(name=(province or {}).get("name")) if province else None,
        )

    @staticmethod
    def _parse_investment_units_area(data: Optional[dict]) -> Optional[InvestmentUnitsAreaDto]:
        if not data:
            return None
        return InvestmentUnitsAreaDto(
            from_m2=data.get("from"),
            to_m2=data.get("to"),
        )

    @staticmethod
    def _parse_dt_iso(value: Optional[str]) -> Optional[datetime]:
        """
        Handles:
          - "2026-01-26T17:29:19Z"
          - "2026-02-07T11:38:12+01:00"
        """
        if not value:
            return None
        try:
            v = value.replace("Z", "+00:00")
            return datetime.fromisoformat(v)
        except ValueError:
            return None


class AdSearcher:
    def __init__(self):
        self.__scraper = cloudscraper.create_scraper()
        self.__parser = AdSearcherParser()
        self.__base_url = "https://www.otodom.pl/pl/wyniki"

    def search_apartments_for_sale(self):
        url = self.__base_url + "/sprzedaz/mieszkanie"

    def search_apartments_for_rent(self):
        url = self.__base_url + "/wynajem/mieszkanie"

    def get_link(
            self,
            offer_type: str,
            object_type: str,
            voivodeship: str,
            city: str,
            district: str
    ):
        url = self.__base_url + f"/{offer_type}/{object_type}/{voivodeship}/{city}/{district}"

    def test(self) -> list[SearchAdDto]:
        url = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/wielkopolskie/poznan/poznan/poznan?limit=36&by=DEFAULT&direction=DESC"
        response = self.__scraper.get(url)
        if response.status_code != 200:
            raise Exception(f"Error getting page: {response.status_code} - {url}")
        text = response.text
        soup = BeautifulSoup(text, 'html.parser')
        ad_json_text = soup.find(name='script', attrs={'type': 'application/json'})
        ad_json = json.loads(ad_json_text.text)
        logger.info("Successfully scraped page")
        return self.__parser.parse(ad_json)


if __name__ == "__main__":
    _searcher = AdSearcher()
    _searcher.test()
