import enum
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import (
    BigInteger, Integer, SmallInteger, String, Text, Numeric, DateTime, ForeignKey, Index, UniqueConstraint, Enum, func,
    LargeBinary
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .ad_dto import DistrictDto, CityDto, CountyDto, ProvinceDto, OwnerDto, AdDto, ImageDto, CharacteristicDto, \
    CharacteristicKey


class AdStatus(str, enum.Enum):
    ACTIVE = "active"
    OUTDATED = "outdated"
    REMOVED = "removed"
    REMOVED_BY_PARENT_AD = "removed_by_parent_ad"
    REMOVED_BY_USER = "removed_by_user"


class ScreeningStatus(str, enum.Enum):
    PASSED = "passed"
    REJECTED = "rejected"
    FAILED = "failed"


class EvaluationStatus(str, enum.Enum):
    OK = "ok"
    NO_IMAGES = "no_images"
    FAILED = "failed"


class TrackingStatus(str, enum.Enum):
    SHORTLISTED = "shortlisted"
    TO_CALL = "to_call"
    CONTACTED = "contacted"
    VIEWING_SCHEDULED = "viewing_scheduled"
    VIEWED = "viewed"
    FAVOURITE = "favourite"
    OFFER_MADE = "offer_made"
    CHOSEN = "chosen"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


DISMISSED_TRACKING_STATUSES = (TrackingStatus.REJECTED, TrackingStatus.UNAVAILABLE)


class EvaluationRequestStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"
    REJECTED = "rejected"
    FAILED = "failed"


class AssistantCallKind(str, enum.Enum):
    INTERPRET = "interpret"
    RANK = "rank"


class RenovationNeeded(str, enum.Enum):
    NONE = "none"
    COSMETIC = "cosmetic"
    PARTIAL = "partial"
    FULL = "full"


def enum_column_type(enum_cls: type[enum.Enum], length: int = 50) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
    )


MASKED_VALUE = "***"


def status_value(status) -> Optional[str]:
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)


def is_masked(value: Optional[str]) -> bool:
    return value is not None and value.strip() == MASKED_VALUE


def _unmasked(new_value: Optional[str], current_value: Optional[str]) -> Optional[str]:
    if is_masked(new_value) and current_value:
        return current_value
    return new_value


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

    status: Mapped[str] = mapped_column(
        Enum(
            AdStatus,
            native_enum=False,
            length=50,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    market: Mapped[Optional[str]] = mapped_column(String(50))
    advertiser_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Not present in the scraped ad JSON - derived from the SearchUrl the ad was found under
    offer_type: Mapped[Optional[str]] = mapped_column(String(50))
    object_type: Mapped[Optional[str]] = mapped_column(String(50))

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
        Index('idx_ads_offer_type', 'offer_type'),
        Index('idx_ads_object_type', 'object_type'),
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

    def update(self, ad_data: AdDto, offer_type: Optional[str] = None, object_type: Optional[str] = None):
        self.title = _unmasked(ad_data.title, self.title)
        self.url = ad_data.url
        self.description = _unmasked(ad_data.description, self.description)
        self.status = ad_data.status
        self.offer_type = offer_type
        self.object_type = object_type
        self.price_value = ad_data.price.value
        self.price_currency = ad_data.price.currency
        self.price_per_m2 = ad_data.price.per_m2
        self.modified_at = ad_data.modified_at
        self.scraped_at = datetime.now()
        self._set_properties(ad_data)
        self._fill_location(ad_data)

    def _fill_location(self, ad_data: AdDto):
        location = ad_data.location
        address = location.address if location else None
        coordinates = location.coordinates if location else None

        if address:
            if address.province:
                self.province_id = address.province.id
            if address.county:
                self.county_id = address.county.id
            if address.city:
                self.city_id = address.city.id
            if address.district:
                self.district_id = address.district.id
            if address.street and not is_masked(address.street.name):
                self.street = address.street.name
            if address.postal_code:
                self.postal_code = address.postal_code
        if coordinates and coordinates.latitude and coordinates.longitude:
            self.latitude = coordinates.latitude
            self.longitude = coordinates.longitude
            self.location_point = self._create_location_point(coordinates)

    def outdate(self):
        self.status = AdStatus.OUTDATED
        self.scraped_at = datetime.now()

    def should_update(self, update_if_older_than_days: int) -> bool:
        if update_if_older_than_days == 0:
            return True
        now = datetime.now(timezone.utc)

        scraped_at = self.scraped_at or self.modified_at
        if scraped_at.tzinfo is None:
            scraped_at = scraped_at.replace(tzinfo=timezone.utc)

        threshold = now - timedelta(days=update_if_older_than_days)
        return scraped_at < threshold

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

    def _set_properties(self, ad_data: AdDto):
        if ad_data.property:
            self.rent_value = ad_data.property.rent.value if ad_data.property.rent else None
            self.rent_currency = ad_data.property.rent.currency if ad_data.property.rent else None
            self.property_type = ad_data.property.type
            self.property_condition = ad_data.property.condition
            self.property_ownership = ad_data.property.ownership
            self.area_value = ad_data.property.area.value
            self.area_unit = ad_data.property.area.unit
            self.flat_floor = ad_data.property.flat_properties.floor
            self.flat_number_of_rooms = ad_data.property.flat_properties.number_of_rooms
            self.building_year = ad_data.property.building_properties.year
            self.building_type = ad_data.property.building_properties.type
            self.building_material = ad_data.property.building_properties.material
            self.building_heating = ad_data.property.building_properties.heating
            self.building_number_of_floors = ad_data.property.building_properties.number_of_floors
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
                self.area_value = m_characteristic.get_value(float)
                self.area_unit = m_characteristic.currency or "M2"

            if rent_characteristic:
                self.rent_value = rent_characteristic.get_value(int)
                self.rent_currency = rent_characteristic.currency or "PLN"

            if flat_floor_characteristic:
                self.flat_floor = flat_floor_characteristic.get_value(str).upper()

            if building_number_of_floors_characteristic:
                self.building_number_of_floors = building_number_of_floors_characteristic.get_value(int)

            if flat_number_of_rooms_characteristic:
                self.flat_number_of_rooms = flat_number_of_rooms_characteristic.get_value(int)

            if building_year_characteristic:
                self.building_year = building_year_characteristic.get_value(int)

            if building_type_characteristic:
                self.building_type = building_type_characteristic.get_value(str).upper()

            if building_material_characteristic:
                self.building_material = building_material_characteristic.get_value(str).upper()

            if building_heating_characteristic:
                self.building_heating = building_heating_characteristic.get_value(str).upper()

    def __repr__(self):
        return f"<Ad(id={self.id}, title={self.title[:30]}...)>"

    @classmethod
    def from_dataclass(
            cls,
            ad_data: AdDto,
            offer_type: Optional[str] = None,
            object_type: Optional[str] = None
    ) -> 'Ad':

        location = ad_data.location
        address = location.address if location else None
        coordinates = location.coordinates if location else None

        ad = cls(
            owner_id=ad_data.owner.id if ad_data.owner else None,
            province_id=address.province.id if address and address.province else None,
            county_id=address.county.id if address and address.county else None,
            city_id=address.city.id if address and address.city else None,
            district_id=address.district.id if address and address.district else None,

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
            offer_type=offer_type,
            object_type=object_type,
            price_value=ad_data.price.value,
            price_currency=ad_data.price.currency,
            price_per_m2=ad_data.price.per_m2,
            latitude=coordinates.latitude if coordinates else None,
            longitude=coordinates.longitude if coordinates else None,
            location_point=cls._create_location_point(coordinates) if coordinates else None,
            street=address.street.name if address and address.street else None,
            postal_code=address.postal_code if address else None,
        )

        ad._set_properties(ad_data)
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


class AdScreening(Base):
    __tablename__ = 'ad_screenings'

    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), primary_key=True
    )
    status: Mapped[str] = mapped_column(enum_column_type(ScreeningStatus), nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    extracted_attributes: Mapped[Optional[dict]] = mapped_column(JSONB)

    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ad_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=1)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    screened_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    ad: Mapped["Ad"] = relationship()

    __table_args__ = (
        Index('idx_ad_screenings_status', 'status'),
        Index('idx_ad_screenings_fingerprint', 'content_fingerprint'),
        Index('idx_ad_screenings_attributes', 'extracted_attributes', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<AdScreening(ad_id={self.ad_id}, status={self.status})>"


class AdEvaluation(Base):
    __tablename__ = 'ad_evaluations'

    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), primary_key=True
    )
    status: Mapped[str] = mapped_column(enum_column_type(EvaluationStatus), nullable=False)

    overall_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    finish_quality_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    freshness_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    move_in_readiness_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    layout_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    natural_light_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    building_condition_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    location_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    value_for_money_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    photo_trust_score: Mapped[Optional[int]] = mapped_column(SmallInteger)

    renovation_needed: Mapped[Optional[str]] = mapped_column(enum_column_type(RenovationNeeded, 20))
    style_tag: Mapped[Optional[str]] = mapped_column(String(50))

    summary: Mapped[Optional[str]] = mapped_column(Text)
    strengths: Mapped[Optional[list]] = mapped_column(JSONB)
    concerns: Mapped[Optional[list]] = mapped_column(JSONB)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)

    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ad_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    price_at_evaluation: Mapped[Optional[int]] = mapped_column(Integer)
    images_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=1)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    ad: Mapped["Ad"] = relationship()

    __table_args__ = (
        Index('idx_ad_evaluations_status', 'status'),
        Index('idx_ad_evaluations_overall_score', 'overall_score'),
        Index('idx_ad_evaluations_finish_quality_score', 'finish_quality_score'),
        Index('idx_ad_evaluations_freshness_score', 'freshness_score'),
        Index('idx_ad_evaluations_move_in_readiness_score', 'move_in_readiness_score'),
        Index('idx_ad_evaluations_value_for_money_score', 'value_for_money_score'),
        Index('idx_ad_evaluations_photo_trust_score', 'photo_trust_score'),
        Index('idx_ad_evaluations_renovation_needed', 'renovation_needed'),
        Index('idx_ad_evaluations_style_tag', 'style_tag'),
        Index('idx_ad_evaluations_fingerprint', 'content_fingerprint'),
        Index('idx_ad_evaluations_attributes', 'attributes', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<AdEvaluation(ad_id={self.ad_id}, overall_score={self.overall_score})>"


class ServiceStatus(str, enum.Enum):
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    FAILED = "failed"
    STOPPED = "stopped"


class ServiceHeartbeat(Base):
    __tablename__ = 'service_heartbeats'

    service: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(enum_column_type(ServiceStatus, 30), nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(100))
    detail: Mapped[Optional[dict]] = mapped_column(JSONB)
    command: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self):
        return f"<ServiceHeartbeat(service={self.service}, status={self.status})>"


class ServiceLog(Base):
    __tablename__ = 'service_logs'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    logger_name: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_service_logs_service_id', 'service', 'id'),
        Index('idx_service_logs_logged_at', 'logged_at'),
    )

    def __repr__(self):
        return f"<ServiceLog(service={self.service}, level={self.level})>"


class SavedSearch(Base):
    __tablename__ = 'saved_searches'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    query: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    def __repr__(self):
        return f"<SavedSearch(id={self.id}, name={self.name})>"


class AdTracking(Base):
    __tablename__ = 'ad_tracking'

    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), primary_key=True
    )
    status: Mapped[str] = mapped_column(enum_column_type(TrackingStatus, 30), nullable=False)
    viewing_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    offer_amount: Mapped[Optional[int]] = mapped_column(Integer)
    price_at_save: Mapped[Optional[int]] = mapped_column(Integer)
    last_comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(50))

    ad: Mapped["Ad"] = relationship()
    events: Mapped[List["AdTrackingEvent"]] = relationship(
        back_populates="tracking",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AdTrackingEvent.created_at.desc()",
    )

    __table_args__ = (
        Index('idx_ad_tracking_status', 'status'),
        Index('idx_ad_tracking_viewing_at', 'viewing_at'),
    )

    def __repr__(self):
        return f"<AdTracking(ad_id={self.ad_id}, status={self.status})>"


class AdTrackingEvent(Base):
    __tablename__ = 'ad_tracking_events'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ad_tracking.ad_id', ondelete='CASCADE'), nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(enum_column_type(TrackingStatus, 30))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    viewing_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger)
    offer_amount: Mapped[Optional[int]] = mapped_column(Integer)
    author: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tracking: Mapped["AdTracking"] = relationship(back_populates="events")

    __table_args__ = (
        Index('idx_ad_tracking_events_ad_id_created_at', 'ad_id', 'created_at'),
    )

    def __repr__(self):
        return f"<AdTrackingEvent(ad_id={self.ad_id}, status={self.status})>"


class AdRawPayload(Base):
    __tablename__ = 'ad_raw_payloads'

    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), primary_key=True
    )
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self):
        return f"<AdRawPayload(ad_id={self.ad_id}, bytes={len(self.payload or b'')})>"


class AdEvaluationRequest(Base):
    __tablename__ = 'ad_evaluation_requests'

    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), primary_key=True
    )
    status: Mapped[str] = mapped_column(enum_column_type(EvaluationRequestStatus, 20), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    requested_by: Mapped[Optional[str]] = mapped_column(String(100))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index('idx_ad_evaluation_requests_status', 'status', 'requested_at'),
    )

    def __repr__(self):
        return f"<AdEvaluationRequest(ad_id={self.ad_id}, status={self.status})>"


class AssistantCall(Base):
    __tablename__ = 'assistant_calls'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(enum_column_type(AssistantCallKind, 20), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(100))
    message: Mapped[Optional[str]] = mapped_column(Text)
    request: Mapped[Optional[dict]] = mapped_column(JSONB)
    response: Mapped[Optional[dict]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_assistant_calls_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<AssistantCall(id={self.id}, kind={self.kind})>"


class AdPriceObservation(Base):
    __tablename__ = 'ad_price_observations'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price_value: Mapped[int] = mapped_column(Integer, nullable=False)
    area_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    status: Mapped[Optional[str]] = mapped_column(String(50))

    __table_args__ = (
        Index('idx_ad_price_observations_ad_id_observed_at', 'ad_id', 'observed_at'),
    )

    def __repr__(self):
        return f"<AdPriceObservation(ad_id={self.ad_id}, price={self.price_value})>"


class AdminArea(Base):
    __tablename__ = 'admin_areas'

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city_name: Mapped[Optional[str]] = mapped_column(String(200))
    province_code: Mapped[str] = mapped_column(String(2), nullable=False)
    geom = mapped_column(Geometry('MULTIPOLYGON', srid=4326), nullable=False)

    __table_args__ = (
        Index('idx_admin_areas_level_city_name', 'level', 'city_name'),
    )

    def __repr__(self):
        return f"<AdminArea(code={self.code}, name={self.name})>"


class AdMarketSignals(Base):
    __tablename__ = 'ad_market_signals'

    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('ads.id', ondelete='CASCADE'), primary_key=True
    )
    listing_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    listings_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    active_listings_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    advertisers_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    first_listed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    days_on_market: Mapped[int] = mapped_column(Integer, nullable=False)
    first_price: Mapped[Optional[int]] = mapped_column(Integer)
    lowest_price: Mapped[Optional[int]] = mapped_column(Integer)
    highest_price: Mapped[Optional[int]] = mapped_column(Integer)
    price_change_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))

    comparables_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    comparables_radius_m: Mapped[Optional[int]] = mapped_column(Integer)
    comparables_median_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    comparables_p25_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    comparables_p75_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    price_vs_comparables_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))

    transactions_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    transactions_radius_m: Mapped[Optional[int]] = mapped_column(Integer)
    transactions_median_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    transactions_p25_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    transactions_p75_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    price_vs_transactions_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    street_transactions_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    street_transactions_median_price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)
    price_vs_street_transactions_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))

    pin_city_name: Mapped[Optional[str]] = mapped_column(String(200))
    pin_gmina_name: Mapped[Optional[str]] = mapped_column(String(200))
    city_border_distance_m: Mapped[Optional[int]] = mapped_column(Integer)
    location_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    location_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    area_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    area_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    previous_sale_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    previous_sale_price: Mapped[Optional[int]] = mapped_column(Integer)
    previous_sale_distance_m: Mapped[Optional[int]] = mapped_column(Integer)
    expressway_distance_m: Mapped[Optional[int]] = mapped_column(Integer)
    expressway_label: Mapped[Optional[str]] = mapped_column(Text)
    railway_distance_m: Mapped[Optional[int]] = mapped_column(Integer)
    runway_approach_m: Mapped[Optional[int]] = mapped_column(Integer)
    nuisance_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    nuisance_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_ad_market_signals_group', 'listing_group_id'),
        Index('idx_ad_market_signals_days_on_market', 'days_on_market'),
        Index('idx_ad_market_signals_price_vs_comparables', 'price_vs_comparables_pct'),
        Index('idx_ad_market_signals_location_flags', 'location_flags', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<AdMarketSignals(ad_id={self.ad_id}, days_on_market={self.days_on_market})>"


class RcnTransaction(Base):
    __tablename__ = 'rcn_transactions'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    teryt: Mapped[Optional[str]] = mapped_column(String(10))
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    document: Mapped[Optional[str]] = mapped_column(Text)
    transaction_key: Mapped[Optional[str]] = mapped_column(Text)
    market: Mapped[Optional[str]] = mapped_column(String(50))
    transaction_kind: Mapped[Optional[str]] = mapped_column(String(100))
    function: Mapped[Optional[str]] = mapped_column(String(100))
    share: Mapped[Optional[str]] = mapped_column(String(50))
    transaction_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2))
    area_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    appurtenant_area: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    floor: Mapped[Optional[int]] = mapped_column(SmallInteger)
    address: Mapped[Optional[str]] = mapped_column(Text)
    location_point = mapped_column(Geometry('POINT', srid=4326), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_rcn_transactions_date', 'transaction_date'),
        Index('idx_rcn_transactions_key', 'transaction_key'),
    )

    def __repr__(self):
        return f"<RcnTransaction(id={self.id}, price={self.transaction_price})>"


class NuisanceFeature(Base):
    __tablename__ = 'nuisance_features'

    osm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(Text)
    geom = mapped_column(Geometry('LINESTRING', srid=4326), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_nuisance_features_kind', 'kind'),
    )

    def __repr__(self):
        return f"<NuisanceFeature(osm_id={self.osm_id}, kind={self.kind}, label={self.label})>"


class OsmStreet(Base):
    __tablename__ = 'osm_streets'

    osm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    geom = mapped_column(Geometry('LINESTRING', srid=4326), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_osm_streets_key', 'key'),
    )

    def __repr__(self):
        return f"<OsmStreet(osm_id={self.osm_id}, name={self.name})>"
