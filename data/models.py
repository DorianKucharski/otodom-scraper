from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import (
    BigInteger, Integer, String, Text, Numeric, DateTime, ForeignKey, Index, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .ad_dto import DistrictDto, CityDto, CountyDto, ProvinceDto, OwnerDto, AdDto, ImageDto, CharacteristicDto, \
    CharacteristicKey


class Base(DeclarativeBase):
    pass


class Province(Base):
    __tablename__ = 'provinces'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="province")

    def __repr__(self):
        return f"<Province(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: ProvinceDto) -> Optional['Province']:
        if not data:
            return None

        return cls(id=data.id, code=data.code, name=data.name)


class County(Base):
    __tablename__ = 'counties'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="county")

    def __repr__(self):
        return f"<County(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: CountyDto) -> Optional['County']:
        if not data:
            return None
        return cls(id=data.id, code=data.code, name=data.name)


class City(Base):
    __tablename__ = 'cities'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="city")

    __table_args__ = (
        Index('idx_cities_name', 'name', postgresql_using='gin',
              postgresql_ops={'name': 'gin_trgm_ops'}),
    )

    def __repr__(self):
        return f"<City(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: CityDto) -> Optional['City']:
        if not data:
            return None
        return cls(id=data.id, code=data.code, name=data.name)


class District(Base):
    __tablename__ = 'districts'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="district")

    __table_args__ = (
        Index('idx_districts_name', 'name', postgresql_using='gin',
              postgresql_ops={'name': 'gin_trgm_ops'}),
    )

    def __repr__(self):
        return f"<District(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: DistrictDto) -> Optional['District']:
        if not data:
            return None
        return cls(id=data.id, code=data.code, name=data.name)


class Owner(Base):
    __tablename__ = 'owners'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    phones: Mapped[List["OwnerPhone"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    ads: Mapped[List["Ad"]] = relationship(back_populates="owner")

    __table_args__ = (
        Index('idx_owners_type', 'type'),
    )

    def __repr__(self):
        return f"<Owner(id={self.id}, name={self.name}, type={self.type})>"

    @classmethod
    def from_dataclass(cls, owner_data: OwnerDto) -> Optional['Owner']:
        if not owner_data:
            return None

        return cls(
            id=owner_data.id,
            name=owner_data.name,
            type=owner_data.type,
            phones=[OwnerPhone(phone=phone_number) for phone_number in owner_data.phones]
        )


class OwnerPhone(Base):
    __tablename__ = 'owner_phones'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('owners.id', ondelete='CASCADE'), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False)

    owner: Mapped["Owner"] = relationship(back_populates="phones")

    __table_args__ = (
        UniqueConstraint('owner_id', 'phone', name='uq_owner_phone'),
    )

    def __repr__(self):
        return f"<OwnerPhone(owner_id={self.owner_id}, phone={self.phone})>"


class Ad(Base):
    __tablename__ = 'ads'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    slug: Mapped[Optional[str]] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[Optional[str]] = mapped_column(String(50))
    advertiser_type: Mapped[Optional[str]] = mapped_column(String(50))

    price_value: Mapped[int] = mapped_column(Integer, nullable=False)
    price_currency: Mapped[str] = mapped_column(String(10), default='PLN')
    price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)

    rent_value: Mapped[Optional[int]] = mapped_column(Integer)
    rent_currency: Mapped[Optional[str]] = mapped_column(String(10))

    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    location_point = mapped_column(Geometry('POINT', srid=4326))

    street: Mapped[Optional[str]] = mapped_column(String(500))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    district_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('districts.id')
    )
    city_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('cities.id')
    )
    county_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('counties.id')
    )
    province_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('provinces.id')
    )

    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    property_condition: Mapped[Optional[str]] = mapped_column(String(50))
    property_ownership: Mapped[Optional[str]] = mapped_column(String(100))

    area_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    area_unit: Mapped[str] = mapped_column(String(10), default='M2')

    flat_floor: Mapped[Optional[str]] = mapped_column(String(50))
    flat_number_of_rooms: Mapped[Optional[int]] = mapped_column(Integer)

    building_year: Mapped[Optional[int]] = mapped_column(Integer)
    building_type: Mapped[Optional[str]] = mapped_column(String(50))
    building_material: Mapped[Optional[str]] = mapped_column(String(50))
    building_heating: Mapped[Optional[str]] = mapped_column(String(50))
    building_number_of_floors: Mapped[Optional[int]] = mapped_column(Integer)

    owner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('owners.id')
    )

    owner: Mapped[Optional["Owner"]] = relationship(back_populates="ads")
    district: Mapped[Optional["District"]] = relationship(back_populates="ads")
    city: Mapped[Optional["City"]] = relationship(back_populates="ads")
    county: Mapped[Optional["County"]] = relationship(back_populates="ads")
    province: Mapped[Optional["Province"]] = relationship(back_populates="ads")

    images: Mapped[List["AdImage"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    features: Mapped[List["AdFeature"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    characteristics: Mapped[List["AdCharacteristic"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    flat_equipment: Mapped[List["AdFlatEquipment"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    flat_areas: Mapped[List["AdFlatArea"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    flat_parking: Mapped[List["AdFlatParking"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    building_windows: Mapped[List["AdBuildingWindow"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    building_conveniences: Mapped[List["AdBuildingConvenience"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )
    building_security: Mapped[List["AdBuildingSecurity"]] = relationship(
        back_populates="ad", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_ads_created_at', 'created_at'),
        Index('idx_ads_price_value', 'price_value'),
        Index('idx_ads_price_per_m2', 'price_per_m2'),
        Index('idx_ads_area_value', 'area_value'),
        Index('idx_ads_market', 'market'),
        Index('idx_ads_status', 'status'),
        Index('idx_ads_city_id', 'city_id'),
        Index('idx_ads_district_id', 'district_id'),
        Index('idx_ads_property_type', 'property_type'),
        Index('idx_ads_flat_number_of_rooms', 'flat_number_of_rooms'),
        Index('idx_ads_building_year', 'building_year'),
        Index('idx_ads_title', 'title', postgresql_using='gin',
              postgresql_ops={'title': 'gin_trgm_ops'}),
        Index('idx_ads_description', 'description', postgresql_using='gin',
              postgresql_ops={'description': 'gin_trgm_ops'}),
        Index('idx_ads_city_price', 'city_id', 'price_value'),
        Index('idx_ads_district_price', 'district_id', 'price_value'),
        Index('idx_ads_location_price', 'city_id', 'district_id', 'price_value'),
        Index('idx_ads_type_rooms_price', 'property_type', 'flat_number_of_rooms', 'price_value'),
        Index('idx_ads_city_type_price', 'city_id', 'property_type', 'price_value'),
    )

    def update(self, ad_data: AdDto):
        self.title = ad_data.title
        self.description = ad_data.description
        self.status = ad_data.status
        self.price_value = ad_data.price.value
        self.price_currency = ad_data.price.currency
        self.price_per_m2 = ad_data.price.per_m2
        self.modified_at = datetime.now()

    def should_update(self, update_if_older_than_days: int) -> bool:
        now = datetime.now(timezone.utc)

        modified_at = self.modified_at
        if modified_at.tzinfo is None:
            modified_at = modified_at.replace(tzinfo=timezone.utc)

        threshold = now - timedelta(days=update_if_older_than_days)
        return modified_at < threshold

    def _populate_relations(self, ad_data: AdDto):
        for img in ad_data.images:
            self.images.append(AdImage.from_dataclass(img))

        for feature in ad_data.features:
            self.features.append(AdFeature(feature=feature))

        for char in ad_data.characteristics:
            self.characteristics.append(AdCharacteristic.from_dataclass(char))

        if ad_data.property:
            for eq in ad_data.property.flat_properties.equipment:
                self.flat_equipment.append(AdFlatEquipment(equipment=eq))

            for area in ad_data.property.flat_properties.areas:
                self.flat_areas.append(AdFlatArea(area=area))

            for parking in ad_data.property.flat_properties.parking:
                self.flat_parking.append(AdFlatParking(parking=parking))

            for window in ad_data.property.building_properties.windows:
                self.building_windows.append(AdBuildingWindow(window_type=window))

            for conv in ad_data.property.building_properties.conveniences:
                self.building_conveniences.append(AdBuildingConvenience(convenience=conv))

            for sec in ad_data.property.building_properties.security:
                self.building_security.append(AdBuildingSecurity(security=sec))

    def __repr__(self):
        return f"<Ad(id={self.id}, title={self.title[:30]}...)>"

    @classmethod
    def from_dataclass(cls, ad_data: AdDto) -> 'Ad':

        ad = cls(
            owner_id=ad_data.owner.id if ad_data.owner else None,
            province_id=ad_data.location.address.province.id if ad_data.location.address.province else None,
            county_id=ad_data.location.address.county.id if ad_data.location.address.county else None,
            city_id=ad_data.location.address.city.id if ad_data.location.address.city else None,
            district_id=ad_data.location.address.district.id if ad_data.location.address.district else None,

            id=ad_data.id,
            public_id=ad_data.public_id if ad_data.public_id else None,
            slug=ad_data.slug,
            url=ad_data.url,
            title=ad_data.title,
            description=ad_data.description,
            created_at=ad_data.created_at,
            modified_at=ad_data.modified_at,
            status=ad_data.status,
            market=ad_data.market,
            advertiser_type=ad_data.advertiser_type,
            price_value=ad_data.price.value,
            price_currency=ad_data.price.currency,
            price_per_m2=ad_data.price.per_m2,
            latitude=ad_data.location.coordinates.latitude,
            longitude=ad_data.location.coordinates.longitude,
            location_point=cls._create_location_point(ad_data.location.coordinates),
            street=ad_data.location.address.street.name if ad_data.location.address.street else None,
            postal_code=ad_data.location.address.postal_code,
        )

        if ad_data.property:
            ad.rent_value = ad_data.property.rent.value if ad_data.property.rent else None
            ad.rent_currency = ad_data.property.rent.currency if ad_data.property.rent else None
            ad.property_type = ad_data.property.type
            ad.property_condition = ad_data.property.condition
            ad.property_ownership = ad_data.property.ownership
            ad.area_value = ad_data.property.area.value
            ad.area_unit = ad_data.property.area.unit
            ad.flat_floor = ad_data.property.flat_properties.floor
            ad.flat_number_of_rooms = ad_data.property.flat_properties.number_of_rooms
            ad.building_year = ad_data.property.building_properties.year
            ad.building_type = ad_data.property.building_properties.type
            ad.building_material = ad_data.property.building_properties.material
            ad.building_heating = ad_data.property.building_properties.heating
            ad.building_number_of_floors = ad_data.property.building_properties.number_of_floors
        else:
            m_characteristic = ad_data.get_characteristic(CharacteristicKey.M)
            rent_characteristic = ad_data.get_characteristic(CharacteristicKey.RENT)
            flat_floor_characteristic = ad_data.get_characteristic(CharacteristicKey.FLOOR_NO)
            building_number_of_floors_characteristic = ad_data.get_characteristic(CharacteristicKey.BUILDING_FLOORS_NUM)
            flat_number_of_rooms_characteristic = ad_data.get_characteristic(CharacteristicKey.ROOMS_NUM)
            building_year_characteristic = ad_data.get_characteristic(CharacteristicKey.BUILD_YEAR)
            building_type_characteristic = ad_data.get_characteristic(CharacteristicKey.BUILDING_TYPE)
            building_material_characteristic = ad_data.get_characteristic(CharacteristicKey.BUILDING_MATERIAL)
            building_heating_characteristic = ad_data.get_characteristic(CharacteristicKey.HEATING)

            if m_characteristic:
                ad.area_value = m_characteristic.get_value(float)
                ad.area_unit = m_characteristic.currency or "M2"

            if rent_characteristic:
                ad.rent_value = rent_characteristic.get_value(int)
                ad.rent_currency = rent_characteristic.currency or "PLN"

            if flat_floor_characteristic:
                ad.flat_floor = flat_floor_characteristic.get_value(str).upper()

            if building_number_of_floors_characteristic:
                ad.building_number_of_floors = building_number_of_floors_characteristic.get_value(int)

            if flat_number_of_rooms_characteristic:
                ad.flat_number_of_rooms = flat_number_of_rooms_characteristic.get_value(int)

            if building_year_characteristic:
                ad.building_year = building_year_characteristic.get_value(int)

            if building_type_characteristic:
                ad.building_type = building_type_characteristic.get_value(str).upper()

            if building_material_characteristic:
                ad.building_material = building_material_characteristic.get_value(str).upper()

            if building_heating_characteristic:
                ad.building_heating = building_heating_characteristic.get_value(str).upper()

        ad._populate_relations(ad_data)
        return ad

    @staticmethod
    def _create_location_point(coords):
        if coords.latitude and coords.longitude:
            return WKTElement(
                f'POINT({coords.longitude} {coords.latitude})',
                srid=4326
            )
        return None


# ============================================================================
# DETAIL TABLES (Lists and arrays)
# ============================================================================

class AdImage(Base):
    __tablename__ = 'ad_images'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbnail: Mapped[str] = mapped_column(Text, nullable=False)
    small: Mapped[str] = mapped_column(Text, nullable=False)
    medium: Mapped[str] = mapped_column(Text, nullable=False)
    large: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="images")

    # Constraints
    __table_args__ = (
        UniqueConstraint('ad_id', 'position', name='uq_ad_image_position'),
        Index('idx_ad_images_ad_id', 'ad_id'),
    )

    def __repr__(self):
        return f"<AdImage(ad_id={self.ad_id}, position={self.position})>"

    @classmethod
    def from_dataclass(cls, data: ImageDto) -> 'AdImage':
        return AdImage(
            position=data.position,
            thumbnail=data.thumbnail,
            small=data.small,
            medium=data.medium,
            large=data.large
        )


class AdFeature(Base):
    __tablename__ = 'ad_features'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    feature: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="features")

    __table_args__ = (
        UniqueConstraint('ad_id', 'feature', name='uq_ad_feature'),
        Index('idx_ad_features_ad_id', 'ad_id'),
        Index('idx_ad_features_feature', 'feature'),
    )

    def __repr__(self):
        return f"<AdFeature(ad_id={self.ad_id}, feature={self.feature})>"


class AdCharacteristic(Base):
    __tablename__ = 'ad_characteristics'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    localized_value: Mapped[Optional[str]] = mapped_column(Text)
    currency: Mapped[Optional[str]] = mapped_column(String(10))

    ad: Mapped["Ad"] = relationship(back_populates="characteristics")

    __table_args__ = (
        UniqueConstraint('ad_id', 'key', name='uq_ad_characteristic'),
        Index('idx_ad_characteristics_ad_id', 'ad_id'),
        Index('idx_ad_characteristics_key', 'key'),
    )

    def __repr__(self):
        return f"<AdCharacteristic(ad_id={self.ad_id}, key={self.key})>"

    @staticmethod
    def from_dataclass(data: CharacteristicDto) -> 'AdCharacteristic':
        return AdCharacteristic(
            key=data.key,
            value=data.value,
            localized_value=data.localized_value,
            currency=data.currency
        )


class AdFlatEquipment(Base):
    __tablename__ = 'ad_flat_equipment'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    equipment: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="flat_equipment")

    __table_args__ = (
        UniqueConstraint('ad_id', 'equipment', name='uq_ad_flat_equipment'),
        Index('idx_ad_flat_equipment_ad_id', 'ad_id'),
        Index('idx_ad_flat_equipment_equipment', 'equipment'),
    )

    def __repr__(self):
        return f"<AdFlatEquipment(ad_id={self.ad_id}, equipment={self.equipment})>"


class AdFlatArea(Base):
    __tablename__ = 'ad_flat_areas'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    area: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="flat_areas")

    __table_args__ = (
        UniqueConstraint('ad_id', 'area', name='uq_ad_flat_area'),
        Index('idx_ad_flat_areas_ad_id', 'ad_id'),
        Index('idx_ad_flat_areas_area', 'area'),
    )

    def __repr__(self):
        return f"<AdFlatArea(ad_id={self.ad_id}, area={self.area})>"


class AdFlatParking(Base):
    __tablename__ = 'ad_flat_parking'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    parking: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="flat_parking")

    __table_args__ = (
        UniqueConstraint('ad_id', 'parking', name='uq_ad_flat_parking'),
        Index('idx_ad_flat_parking_ad_id', 'ad_id'),
    )

    def __repr__(self):
        return f"<AdFlatParking(ad_id={self.ad_id}, parking={self.parking})>"


class AdBuildingWindow(Base):
    __tablename__ = 'ad_building_windows'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    window_type: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="building_windows")

    __table_args__ = (
        UniqueConstraint('ad_id', 'window_type', name='uq_ad_building_window'),
        Index('idx_ad_building_windows_ad_id', 'ad_id'),
    )

    def __repr__(self):
        return f"<AdBuildingWindow(ad_id={self.ad_id}, window_type={self.window_type})>"


class AdBuildingConvenience(Base):
    __tablename__ = 'ad_building_conveniences'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    convenience: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="building_conveniences")

    __table_args__ = (
        UniqueConstraint('ad_id', 'convenience', name='uq_ad_building_convenience'),
        Index('idx_ad_building_conveniences_ad_id', 'ad_id'),
        Index('idx_ad_building_conveniences_convenience', 'convenience'),
    )

    def __repr__(self):
        return f"<AdBuildingConvenience(ad_id={self.ad_id}, convenience={self.convenience})>"


class AdBuildingSecurity(Base):
    __tablename__ = 'ad_building_security'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    security: Mapped[str] = mapped_column(String(255), nullable=False)

    ad: Mapped["Ad"] = relationship(back_populates="building_security")

    __table_args__ = (
        UniqueConstraint('ad_id', 'security', name='uq_ad_building_security'),
        Index('idx_ad_building_security_ad_id', 'ad_id'),
        Index('idx_ad_building_security_security', 'security'),
    )

    def __repr__(self):
        return f"<AdBuildingSecurity(ad_id={self.ad_id}, security={self.security})>"
