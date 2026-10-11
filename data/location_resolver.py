from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Iterable, Optional

from .ad_dto import AdDto, AddressDto, CityDto, CountyDto, DistrictDto, LocationHintsDto, ProvinceDto


def synthetic_location_id(level: str, path: str) -> int:
    digest = hashlib.sha256(f"{level}:{path}".encode()).hexdigest()
    return -int(digest[:15], 16)


@dataclass
class LocationIndex:
    province_ids_by_code: dict[str, int] = field(default_factory=dict)
    county_ids_by_code: dict[str, int] = field(default_factory=dict)
    city_ids: set[int] = field(default_factory=set)
    district_ids_by_city_and_code: dict[tuple[int, str], int] = field(default_factory=dict)
    district_ids_by_unique_code: dict[str, int] = field(default_factory=dict)
    district_ids_in_use: set[int] = field(default_factory=set)

    @classmethod
    def build(
            cls,
            provinces: Iterable[tuple[int, str]],
            counties: Iterable[tuple[int, str]],
            city_ids: Iterable[int],
            districts: Iterable[tuple[int, str]],
            district_usage: Iterable[tuple[int, str, int, int]],
    ) -> LocationIndex:
        districts = list(districts)
        codes = Counter(code for _, code in districts)

        best_usage: dict[tuple[int, str], tuple[int, int]] = {}
        district_usage = list(district_usage)
        for city_id, code, district_id, ad_count in district_usage:
            key = (city_id, code)
            if key not in best_usage or ad_count > best_usage[key][1]:
                best_usage[key] = (district_id, ad_count)

        return cls(
            province_ids_by_code={code: province_id for province_id, code in provinces},
            county_ids_by_code={code: county_id for county_id, code in counties},
            city_ids=set(city_ids),
            district_ids_by_city_and_code={key: district_id for key, (district_id, _) in best_usage.items()},
            district_ids_by_unique_code={code: district_id for district_id, code in districts if codes[code] == 1},
            district_ids_in_use={district_id for _, _, district_id, _ in district_usage},
        )


def complete_location(ad: AdDto, index: LocationIndex) -> None:
    location = ad.location
    if location is None or location.hints is None:
        return

    address = location.address or AddressDto(None, None, None, None, None, None)
    location.address = complete_address(address, location.hints, index)


def complete_address(address: AddressDto, hints: LocationHintsDto, index: LocationIndex) -> AddressDto:
    province = address.province or _province(hints, index)
    county = address.county or _county(hints, index)
    city = address.city or _city(hints, index)
    district = address.district or _district(hints, city, index)
    return replace(address, province=province, county=county, city=city, district=district)


def _province(hints: LocationHintsDto, index: LocationIndex) -> Optional[ProvinceDto]:
    if not hints.province_code:
        return None
    province_id = index.province_ids_by_code.get(hints.province_code)
    if province_id is None:
        province_id = synthetic_location_id("province", hints.province_code)
        index.province_ids_by_code[hints.province_code] = province_id
    return ProvinceDto(id=province_id, code=hints.province_code, name=hints.province_name or hints.province_code)


def _county(hints: LocationHintsDto, index: LocationIndex) -> Optional[CountyDto]:
    if not hints.county_code:
        return None
    county_id = index.county_ids_by_code.get(hints.county_code)
    if county_id is None:
        county_id = synthetic_location_id("county", hints.county_code)
        index.county_ids_by_code[hints.county_code] = county_id
    return CountyDto(id=county_id, code=hints.county_code, name=_county_name(hints.county_code))


def _city(hints: LocationHintsDto, index: LocationIndex) -> Optional[CityDto]:
    if not hints.city_code and hints.city_id is None:
        return None
    city_id = hints.city_id
    if city_id is None:
        city_id = synthetic_location_id("city", hints.city_path or hints.city_code)
    index.city_ids.add(city_id)
    code = hints.city_code or str(city_id)
    return CityDto(id=city_id, code=code, name=hints.city_name or code)


def _district(hints: LocationHintsDto, city: Optional[CityDto], index: LocationIndex) -> Optional[DistrictDto]:
    if not hints.district_code:
        return None

    key = (city.id, hints.district_code) if city else None
    district_id = index.district_ids_by_city_and_code.get(key) if key else None
    if district_id is None:
        unique_id = index.district_ids_by_unique_code.get(hints.district_code)
        if unique_id is not None and (key is None or unique_id not in index.district_ids_in_use):
            district_id = unique_id
            if key:
                index.district_ids_by_city_and_code[key] = district_id
                index.district_ids_in_use.add(district_id)
    if district_id is None:
        district_id = synthetic_location_id("district", hints.district_path or hints.district_code)
        if key:
            index.district_ids_by_city_and_code[key] = district_id

    return DistrictDto(id=district_id, code=hints.district_code, name=hints.district_name or hints.district_code)


def _county_name(code: str) -> str:
    name = code.removeprefix("powiat-").replace("-", " ")
    return name[:1].upper() + name[1:]

