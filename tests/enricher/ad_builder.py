from __future__ import annotations

from datetime import datetime
from typing import Optional

from data.models import Ad, AdBuildingConvenience, AdFeature, AdFlatEquipment, AdImage, City, District, Province


class AdBuilder:
    def __init__(self):
        self.__ad = Ad(
            id=1,
            url="https://www.otodom.pl/pl/oferta/test",
            title="Mieszkanie 3 pokoje",
            description="<p>Opis</p>",
            created_at=datetime(2026, 8, 1),
            modified_at=datetime(2026, 8, 10),
            status="active",
            price_value=750_000,
            price_currency="PLN",
            price_per_m2=12_500,
            area_value=60,
            flat_number_of_rooms=3,
            flat_floor="FLOOR_2",
            building_number_of_floors=4,
            building_year=1998,
            market="SECONDARY",
            advertiser_type="private",
            property_type="FLAT",
            property_condition="READY_TO_USE",
            street="Rynek",
        )

    def with_id(self, ad_id: int) -> "AdBuilder":
        self.__ad.id = ad_id
        return self

    def with_title(self, title: str) -> "AdBuilder":
        self.__ad.title = title
        return self

    def with_description(self, description: Optional[str]) -> "AdBuilder":
        self.__ad.description = description
        return self

    def with_price(self, price_value: int, price_per_m2: Optional[int] = None) -> "AdBuilder":
        self.__ad.price_value = price_value
        self.__ad.price_per_m2 = price_per_m2
        return self

    def with_location(self, city: str = "Lublin", district: str = "Stare Miasto") -> "AdBuilder":
        self.__ad.city = City(id=1, code=city.lower(), name=city)
        self.__ad.district = District(id=2, code=district.lower(), name=district)
        self.__ad.province = Province(id=3, code="lubelskie", name="lubelskie")
        self.__ad.city_id = 1
        self.__ad.district_id = 2
        self.__ad.province_id = 3
        return self

    def with_feature(self, feature: str) -> "AdBuilder":
        self.__ad.features.append(AdFeature(feature=feature))
        return self

    def with_equipment(self, equipment: str) -> "AdBuilder":
        self.__ad.flat_equipment.append(AdFlatEquipment(equipment=equipment))
        return self

    def with_convenience(self, convenience: str) -> "AdBuilder":
        self.__ad.building_conveniences.append(AdBuildingConvenience(convenience=convenience))
        return self

    def with_images(self, count: int) -> "AdBuilder":
        for position in range(count):
            self.__ad.images.append(AdImage(
                position=position,
                thumbnail=f"https://cdn/t{position}.jpeg",
                small=f"https://cdn/s{position}.jpeg",
                medium=f"https://cdn/m{position}.jpeg",
                large=f"https://cdn/l{position}.jpeg",
            ))
        return self

    def build(self) -> Ad:
        return self.__ad
