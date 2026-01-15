"""
SQLAlchemy ORM Models for Otodom Scraper
Normalized database schema with PostGIS support
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Integer, String, Text, Numeric, DateTime, Boolean,
    ForeignKey, Index, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from geoalchemy2 import Geometry


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


# ============================================================================
# DIMENSION TABLES (Słowniki)
# ============================================================================

class Province(Base):
    __tablename__ = 'provinces'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    ads: Mapped[List["Ad"]] = relationship(back_populates="province")

    def __repr__(self):
        return f"<Province(id={self.id}, name={self.name})>"


class County(Base):
    __tablename__ = 'counties'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    ads: Mapped[List["Ad"]] = relationship(back_populates="county")

    def __repr__(self):
        return f"<County(id={self.id}, name={self.name})>"


class City(Base):
    __tablename__ = 'cities'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    ads: Mapped[List["Ad"]] = relationship(back_populates="city")

    # Indexes
    __table_args__ = (
        Index('idx_cities_name', 'name', postgresql_using='gin',
              postgresql_ops={'name': 'gin_trgm_ops'}),
    )

    def __repr__(self):
        return f"<City(id={self.id}, name={self.name})>"


class District(Base):
    __tablename__ = 'districts'

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    ads: Mapped[List["Ad"]] = relationship(back_populates="district")

    # Indexes
    __table_args__ = (
        Index('idx_districts_name', 'name', postgresql_using='gin',
              postgresql_ops={'name': 'gin_trgm_ops'}),
    )

    def __repr__(self):
        return f"<District(id={self.id}, name={self.name})>"


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

    # Relationships
    phones: Mapped[List["OwnerPhone"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    ads: Mapped[List["Ad"]] = relationship(back_populates="owner")

    # Indexes
    __table_args__ = (
        Index('idx_owners_type', 'type'),
    )

    def __repr__(self):
        return f"<Owner(id={self.id}, name={self.name}, type={self.type})>"


class OwnerPhone(Base):
    __tablename__ = 'owner_phones'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('owners.id', ondelete='CASCADE'), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    owner: Mapped["Owner"] = relationship(back_populates="phones")

    # Constraints
    __table_args__ = (
        UniqueConstraint('owner_id', 'phone', name='uq_owner_phone'),
    )

    def __repr__(self):
        return f"<OwnerPhone(owner_id={self.owner_id}, phone={self.phone})>"


# ============================================================================
# MAIN FACT TABLE - Ads
# ============================================================================

class Ad(Base):
    __tablename__ = 'ads'

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    slug: Mapped[Optional[str]] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    # Status and classification
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    market: Mapped[Optional[str]] = mapped_column(String(50))
    advertiser_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Price information
    price_value: Mapped[int] = mapped_column(Integer, nullable=False)
    price_currency: Mapped[str] = mapped_column(String(10), default='PLN')
    price_per_m2: Mapped[Optional[int]] = mapped_column(Integer)

    # Rent information
    rent_value: Mapped[Optional[int]] = mapped_column(Integer)
    rent_currency: Mapped[Optional[str]] = mapped_column(String(10))

    # Location - Geography (PostGIS)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    location_point = mapped_column(Geometry('POINT', srid=4326))

    # Location - Administrative
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

    # Property details
    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    property_condition: Mapped[Optional[str]] = mapped_column(String(50))
    property_ownership: Mapped[Optional[str]] = mapped_column(String(100))

    # Area
    area_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    area_unit: Mapped[str] = mapped_column(String(10), default='M2')

    # Flat properties
    flat_floor: Mapped[Optional[str]] = mapped_column(String(50))
    flat_number_of_rooms: Mapped[Optional[int]] = mapped_column(Integer)

    # Building properties
    building_year: Mapped[Optional[int]] = mapped_column(Integer)
    building_type: Mapped[Optional[str]] = mapped_column(String(50))
    building_material: Mapped[Optional[str]] = mapped_column(String(50))
    building_heating: Mapped[Optional[str]] = mapped_column(String(50))
    building_number_of_floors: Mapped[Optional[int]] = mapped_column(Integer)

    # Foreign keys
    owner_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('owners.id')
    )

    # Relationships
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

    # Indexes
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="features")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="characteristics")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="flat_equipment")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="flat_areas")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="flat_parking")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="building_windows")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="building_conveniences")

    # Constraints
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

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="building_security")

    # Constraints
    __table_args__ = (
        UniqueConstraint('ad_id', 'security', name='uq_ad_building_security'),
        Index('idx_ad_building_security_ad_id', 'ad_id'),
        Index('idx_ad_building_security_security', 'security'),
    )

    def __repr__(self):
        return f"<AdBuildingSecurity(ad_id={self.ad_id}, security={self.security})>"
