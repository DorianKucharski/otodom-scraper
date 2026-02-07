from datetime import datetime
from typing import List, Optional

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import (
    BigInteger, Integer, String, Text, Numeric, DateTime, ForeignKey, Index, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session


from ad_scraper import CoordinatesDto, DistrictDto, CityDto, CountyDto, ProvinceDto, AddressDto, LocationDto, PriceDto,AreaDto, RentDto


class Base(DeclarativeBase):
    pass


class Province(Base):
    __tablename__ = 'provinces'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="province")

    def __repr__(self):
        return f"<Province(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: ProvinceDto, session: Session) -> Optional['Province']:
        if not data:
            return None

        province = session.get(cls, data.id)
        if not province:
            province = cls(id=data.id, code=data.code, name=data.name)
            session.add(province)
        return province


class County(Base):
    __tablename__ = 'counties'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="county")

    def __repr__(self):
        return f"<County(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: CountyDto, session: Session) -> Optional['County']:
        if not data:
            return None

        county = session.get(cls, data.id)
        if not county:
            county = cls(id=data.id, code=data.code, name=data.name)
            session.add(county)
        return county


class City(Base):
    __tablename__ = 'cities'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="city")

    __table_args__ = (
        Index('idx_cities_name', 'name', postgresql_using='gin',
              postgresql_ops={'name': 'gin_trgm_ops'}),
    )

    def __repr__(self):
        return f"<City(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: CityDto, session: Session) -> Optional['City']:
        if not data:
            return None

        city = session.get(cls, data.id)
        if not city:
            city = cls(id=data.id, code=data.code, name=data.name)
            session.add(city)
        return city


class District(Base):
    __tablename__ = 'districts'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    ads: Mapped[List["Ad"]] = relationship(back_populates="district")

    __table_args__ = (
        Index('idx_districts_name', 'name', postgresql_using='gin',
              postgresql_ops={'name': 'gin_trgm_ops'}),
    )

    def __repr__(self):
        return f"<District(id={self.id}, name={self.name})>"

    @classmethod
    def from_dataclass(cls, data: DistrictDto, session: Session) -> Optional['District']:
        if not data:
            return None

        district = session.get(cls, data.id)
        if not district:
            district = cls(id=data.id, code=data.code, name=data.name)
            session.add(district)
        return district


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
    def from_dataclass(cls, owner_data, session: Session) -> 'Owner':
        if not owner_data:
            return None

        owner = session.get(cls, owner_data.id)

        if owner:
            owner.name = owner_data.name
            owner.type = owner_data.type

            owner.phones.clear()
            for phone_number in owner_data.phones:
                owner.phones.append(OwnerPhone(phone=phone_number))
        else:
            owner = cls(
                id=owner_data.id,
                name=owner_data.name,
                type=owner_data.type
            )
            for phone_number in owner_data.phones:
                owner.phones.append(OwnerPhone(phone=phone_number))
            session.add(owner)

        session.flush()
        return owner


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
    district_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey('districts.id')
    )
    city_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey('cities.id')
    )
    county_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey('counties.id')
    )
    province_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey('provinces.id')
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
        Index('idx_ads_location_point', 'location_point', postgresql_using='gist'),
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

    def __repr__(self):
        return f"<Ad(id={self.id}, title={self.title[:30]}...)>"

    @classmethod
    def from_dataclass(cls, ad_data: AdDto, session: Session) -> 'Ad':
        addr = ad_data.location.address
        Province.from_dataclass(addr.province, session)
        County.from_dataclass(addr.county, session)
        City.from_dataclass(addr.city, session)
        District.from_dataclass(addr.district, session)

        owner = Owner.from_dataclass(ad_data.owner, session)

        ad = session.get(cls, ad_data.id)

        if ad:
            cls._update_from_dataclass(ad, ad_data, owner, session)
        else:
            ad = cls._create_from_dataclass(ad_data, owner, session)
            session.add(ad)

        session.flush()
        return ad

    @classmethod
    def _create_from_dataclass(cls, ad_data: AdDto, owner: Owner, session: Session) -> 'Ad':
        addr = ad_data.location.address
        coords = ad_data.location.coordinates

        location_point = None
        if coords.latitude and coords.longitude:
            location_point = WKTElement(
                f'POINT({coords.longitude} {coords.latitude})',
                srid=4326
            )

        ad = cls(
            id=ad_data.id,
            public_id=ad_data.public_id,
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
            rent_value=ad_data.property.rent.value if ad_data.property.rent else None,
            rent_currency=ad_data.property.rent.currency if ad_data.property.rent else None,
            latitude=coords.latitude,
            longitude=coords.longitude,
            location_point=location_point,
            street=addr.street,
            postal_code=addr.postal_code,
            district_id=addr.district.id if addr.district else None,
            city_id=addr.city.id if addr.city else None,
            county_id=addr.county.id if addr.county else None,
            province_id=addr.province.id if addr.province else None,
            property_type=ad_data.property.type,
            property_condition=ad_data.property.condition,
            property_ownership=ad_data.property.ownership,
            area_value=ad_data.property.area.value,
            area_unit=ad_data.property.area.unit,
            flat_floor=ad_data.property.flat_properties.floor,
            flat_number_of_rooms=ad_data.property.flat_properties.number_of_rooms,
            building_year=ad_data.property.building_properties.year,
            building_type=ad_data.property.building_properties.type,
            building_material=ad_data.property.building_properties.material,
            building_heating=ad_data.property.building_properties.heating,
            building_number_of_floors=ad_data.property.building_properties.number_of_floors,
            owner_id=owner.id if owner else None
        )

        for i, img in enumerate(ad_data.images):
            ad.images.append(AdImage(
                position=i,
                thumbnail=img.thumbnail,
                small=img.small,
                medium=img.medium,
                large=img.large
            ))

        for feature in ad_data.features:
            ad.features.append(AdFeature(feature=feature))

        for char in ad_data.characteristics:
            ad.characteristics.append(AdCharacteristic(
                key=char.key,
                value=char.value,
                localized_value=char.localized_value,
                currency=char.currency
            ))

        for eq in ad_data.property.flat_properties.equipment:
            ad.flat_equipment.append(AdFlatEquipment(equipment=eq))

        for area in ad_data.property.flat_properties.areas:
            ad.flat_areas.append(AdFlatArea(area=area))

        for parking in ad_data.property.flat_properties.parking:
            ad.flat_parking.append(AdFlatParking(parking=parking))

        for window in ad_data.property.building_properties.windows:
            ad.building_windows.append(AdBuildingWindow(window_type=window))

        for conv in ad_data.property.building_properties.conveniences:
            ad.building_conveniences.append(AdBuildingConvenience(convenience=conv))

        for sec in ad_data.property.building_properties.security:
            ad.building_security.append(AdBuildingSecurity(security=sec))

        return ad

    @staticmethod
    def _update_from_dataclass(ad: 'Ad', ad_data: AdDto, owner: Owner, session: Session):
        addr = ad_data.location.address
        coords = ad_data.location.coordinates

        ad.public_id = ad_data.public_id
        ad.slug = ad_data.slug
        ad.url = ad_data.url
        ad.title = ad_data.title
        ad.description = ad_data.description
        ad.modified_at = ad_data.modified_at
        ad.status = ad_data.status
        ad.market = ad_data.market
        ad.advertiser_type = ad_data.advertiser_type
        ad.price_value = ad_data.price.value
        ad.price_currency = ad_data.price.currency
        ad.price_per_m2 = ad_data.price.per_m2
        ad.rent_value = ad_data.property.rent.value if ad_data.property.rent else None
        ad.rent_currency = ad_data.property.rent.currency if ad_data.property.rent else None
        ad.latitude = coords.latitude
        ad.longitude = coords.longitude

        if coords.latitude and coords.longitude:
            ad.location_point = WKTElement(
                f'POINT({coords.longitude} {coords.latitude})',
                srid=4326
            )

        ad.street = addr.street
        ad.postal_code = addr.postal_code
        ad.district_id = addr.district.id if addr.district else None
        ad.city_id = addr.city.id if addr.city else None
        ad.county_id = addr.county.id if addr.county else None
        ad.province_id = addr.province.id if addr.province else None
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
        ad.owner_id = owner.id if owner else None

        ad.images.clear()
        ad.features.clear()
        ad.characteristics.clear()
        ad.flat_equipment.clear()
        ad.flat_areas.clear()
        ad.flat_parking.clear()
        ad.building_windows.clear()
        ad.building_conveniences.clear()
        ad.building_security.clear()

        for i, img in enumerate(ad_data.images):
            ad.images.append(AdImage(
                position=i,
                thumbnail=img.thumbnail,
                small=img.small,
                medium=img.medium,
                large=img.large
            ))

        for feature in ad_data.features:
            ad.features.append(AdFeature(feature=feature))

        for char in ad_data.characteristics:
            ad.characteristics.append(AdCharacteristic(
                key=char.key,
                value=char.value,
                localized_value=char.localized_value,
                currency=char.currency
            ))

        for eq in ad_data.property.flat_properties.equipment:
            ad.flat_equipment.append(AdFlatEquipment(equipment=eq))

        for area in ad_data.property.flat_properties.areas:
            ad.flat_areas.append(AdFlatArea(area=area))

        for parking in ad_data.property.flat_properties.parking:
            ad.flat_parking.append(AdFlatParking(parking=parking))

        for window in ad_data.property.building_properties.windows:
            ad.building_windows.append(AdBuildingWindow(window_type=window))

        for conv in ad_data.property.building_properties.conveniences:
            ad.building_conveniences.append(AdBuildingConvenience(convenience=conv))

        for sec in ad_data.property.building_properties.security:
            ad.building_security.append(AdBuildingSecurity(security=sec))

        session.flush()


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
