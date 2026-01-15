"""
Database Manager for Otodom Scraper
Provides high-level database operations using SQLAlchemy ORM
"""

import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, select, func, text, and_, or_
from sqlalchemy.orm import Session, sessionmaker
from geoalchemy2 import func as geo_func
from geoalchemy2.elements import WKTElement

from models import (
    Base, Ad, Owner, OwnerPhone, City, County, Province, District,
    AdImage, AdFeature, AdCharacteristic, AdFlatEquipment, AdFlatArea,
    AdFlatParking, AdBuildingWindow, AdBuildingConvenience, AdBuildingSecurity
)
from parser import Ad as AdDataclass

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager for Otodom ads using SQLAlchemy ORM.

    Example connection string:
    postgresql://user:password@localhost:5432/otodom_db
    """

    def __init__(self, connection_string: str, echo: bool = False):
        """
        Initialize DatabaseManager with SQLAlchemy.

        Args:
            connection_string: PostgreSQL connection string
            echo: Enable SQL query logging (default: False)
        """
        self.engine = create_engine(connection_string, echo=echo)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("Database connection initialized with SQLAlchemy")

    def create_all_tables(self):
        """
        Create all tables defined in models.
        This also creates necessary PostgreSQL extensions.
        """
        # Create extensions first
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            logger.info("PostgreSQL extensions created")

        # Create all tables
        Base.metadata.create_all(self.engine)
        logger.info("All tables created successfully")

    def drop_all_tables(self):
        """Drop all tables. Use with caution!"""
        Base.metadata.drop_all(self.engine)
        logger.warning("All tables dropped")

    @contextmanager
    def get_session(self):
        """
        Context manager for database session.

        Yields:
            SQLAlchemy Session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def save_ad(self, ad_data: AdDataclass) -> int:
        """
        Save or update an ad with all related data (UPSERT).

        Args:
            ad_data: Ad dataclass instance from parser

        Returns:
            The ad ID
        """
        with self.get_session() as session:
            # Save location entities
            self._save_location_entities(session, ad_data)

            # Save or update owner
            owner = self._save_owner(session, ad_data.owner)

            # Check if ad exists
            existing_ad = session.get(Ad, ad_data.id)

            if existing_ad:
                # Update existing ad
                self._update_ad(session, existing_ad, ad_data, owner)
                logger.info(f"Updated ad {ad_data.id}: {ad_data.title}")
            else:
                # Create new ad
                ad = self._create_ad(session, ad_data, owner)
                session.add(ad)
                logger.info(f"Created new ad {ad_data.id}: {ad_data.title}")

            session.flush()

        return ad_data.id

    def _save_location_entities(self, session: Session, ad_data: AdDataclass):
        """Save or update location entities (province, county, city, district)"""
        addr = ad_data.location.address

        if addr.province:
            province = session.get(Province, addr.province.id)
            if not province:
                province = Province(
                    id=addr.province.id,
                    code=addr.province.code,
                    name=addr.province.name
                )
                session.add(province)

        if addr.county:
            county = session.get(County, addr.county.id)
            if not county:
                county = County(
                    id=addr.county.id,
                    code=addr.county.code,
                    name=addr.county.name
                )
                session.add(county)

        if addr.city:
            city = session.get(City, addr.city.id)
            if not city:
                city = City(
                    id=addr.city.id,
                    code=addr.city.code,
                    name=addr.city.name
                )
                session.add(city)

        if addr.district:
            district = session.get(District, addr.district.id)
            if not district:
                district = District(
                    id=addr.district.id,
                    code=addr.district.code,
                    name=addr.district.name
                )
                session.add(district)

        session.flush()

    def _save_owner(self, session: Session, owner_data) -> Owner:
        """Save or update owner"""
        owner = session.get(Owner, owner_data.id)

        if owner:
            # Update existing owner
            owner.name = owner_data.name
            owner.type = owner_data.type

            # Update phones
            # Delete old phones
            for phone in owner.phones:
                session.delete(phone)

            # Add new phones
            for phone_number in owner_data.phones:
                owner.phones.append(OwnerPhone(phone=phone_number))
        else:
            # Create new owner
            owner = Owner(
                id=owner_data.id,
                name=owner_data.name,
                type=owner_data.type
            )
            for phone_number in owner_data.phones:
                owner.phones.append(OwnerPhone(phone=phone_number))
            session.add(owner)

        session.flush()
        return owner

    def _create_ad(self, session: Session, ad_data: AdDataclass, owner: Owner) -> Ad:
        """Create new Ad instance with all relations"""
        addr = ad_data.location.address
        coords = ad_data.location.coordinates

        # Create location point for PostGIS
        location_point = None
        if coords.latitude and coords.longitude:
            location_point = WKTElement(
                f'POINT({coords.longitude} {coords.latitude})',
                srid=4326
            )

        ad = Ad(
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
            owner_id=owner.id
        )

        # Add images
        for i, img in enumerate(ad_data.images):
            ad.images.append(AdImage(
                position=i,
                thumbnail=img.thumbnail,
                small=img.small,
                medium=img.medium,
                large=img.large
            ))

        # Add features
        for feature in ad_data.features:
            ad.features.append(AdFeature(feature=feature))

        # Add characteristics
        for char in ad_data.characteristics:
            ad.characteristics.append(AdCharacteristic(
                key=char.key,
                value=char.value,
                localized_value=char.localized_value,
                currency=char.currency
            ))

        # Add flat equipment
        for eq in ad_data.property.flat_properties.equipment:
            ad.flat_equipment.append(AdFlatEquipment(equipment=eq))

        # Add flat areas
        for area in ad_data.property.flat_properties.areas:
            ad.flat_areas.append(AdFlatArea(area=area))

        # Add flat parking
        for parking in ad_data.property.flat_properties.parking:
            ad.flat_parking.append(AdFlatParking(parking=parking))

        # Add building windows
        for window in ad_data.property.building_properties.windows:
            ad.building_windows.append(AdBuildingWindow(window_type=window))

        # Add building conveniences
        for conv in ad_data.property.building_properties.conveniences:
            ad.building_conveniences.append(AdBuildingConvenience(convenience=conv))

        # Add building security
        for sec in ad_data.property.building_properties.security:
            ad.building_security.append(AdBuildingSecurity(security=sec))

        return ad

    def _update_ad(self, session: Session, ad: Ad, ad_data: AdDataclass, owner: Owner):
        """Update existing Ad with new data"""
        addr = ad_data.location.address
        coords = ad_data.location.coordinates

        # Update basic fields
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

        # Update location point
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
        ad.owner_id = owner.id

        # Delete and recreate related entities (cascade delete-orphan)
        ad.images.clear()
        ad.features.clear()
        ad.characteristics.clear()
        ad.flat_equipment.clear()
        ad.flat_areas.clear()
        ad.flat_parking.clear()
        ad.building_windows.clear()
        ad.building_conveniences.clear()
        ad.building_security.clear()

        # Add new related data
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

    # ========================================================================
    # QUERY METHODS - Advanced searching with SQLAlchemy
    # ========================================================================

    def get_ad_by_id(self, ad_id: int) -> Optional[Ad]:
        """Get ad by ID with all relationships loaded"""
        with self.get_session() as session:
            return session.get(Ad, ad_id)

    def get_ads_by_city(
        self,
        city_name: str,
        limit: int = 100,
        status: str = 'active'
    ) -> List[Ad]:
        """Get ads by city name"""
        with self.get_session() as session:
            stmt = (
                select(Ad)
                .join(City)
                .where(City.name.ilike(f'%{city_name}%'))
                .where(Ad.status == status)
                .order_by(Ad.created_at.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars())

    def get_ads_sorted_by_feature_count(
        self,
        city_id: Optional[str] = None,
        min_features: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get ads sorted by number of features (from most to least).
        Returns list of dicts with ad data and counts.
        """
        with self.get_session() as session:
            # Build query with counts
            query = (
                select(
                    Ad,
                    func.count(AdFeature.id.distinct()).label('features_count'),
                    func.count(AdFlatEquipment.id.distinct()).label('equipment_count'),
                    func.count(AdFlatArea.id.distinct()).label('areas_count')
                )
                .outerjoin(AdFeature)
                .outerjoin(AdFlatEquipment)
                .outerjoin(AdFlatArea)
                .where(Ad.status == 'active')
            )

            if city_id:
                query = query.where(Ad.city_id == city_id)

            query = (
                query
                .group_by(Ad.id)
                .having(func.count(AdFeature.id.distinct()) >= min_features)
                .order_by(
                    func.count(AdFeature.id.distinct()).desc(),
                    func.count(AdFlatEquipment.id.distinct()).desc(),
                    func.count(AdFlatArea.id.distinct()).desc()
                )
                .limit(limit)
            )

            results = []
            for row in session.execute(query):
                ad = row[0]
                results.append({
                    'id': ad.id,
                    'title': ad.title,
                    'price_value': ad.price_value,
                    'price_per_m2': ad.price_per_m2,
                    'area_value': ad.area_value,
                    'features_count': row[1],
                    'equipment_count': row[2],
                    'areas_count': row[3]
                })

            return results

    def get_ads_within_radius(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get ads within radius from a point using PostGIS.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_meters: Radius in meters
            limit: Maximum number of results

        Returns:
            List of dicts with ad data and distance
        """
        with self.get_session() as session:
            point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)

            query = (
                select(
                    Ad,
                    geo_func.ST_Distance(
                        func.cast(Ad.location_point, Geometry),
                        func.cast(point, Geometry)
                    ).label('distance_meters')
                )
                .where(Ad.location_point.isnot(None))
                .where(Ad.status == 'active')
                .where(
                    geo_func.ST_DWithin(
                        func.cast(Ad.location_point, Geometry),
                        func.cast(point, Geometry),
                        radius_meters
                    )
                )
                .order_by(text('distance_meters'))
                .limit(limit)
            )

            results = []
            for row in session.execute(query):
                ad = row[0]
                results.append({
                    'ad_id': ad.id,
                    'title': ad.title,
                    'price_value': ad.price_value,
                    'price_per_m2': ad.price_per_m2,
                    'distance_meters': float(row[1]) if row[1] else None
                })

            return results

    def get_ad_density_stats(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000
    ) -> Dict[str, Any]:
        """
        Get ad density statistics in a circular area.

        Returns:
            Dictionary with density statistics
        """
        with self.get_session() as session:
            point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)

            # Calculate area in km²
            area_km2 = (3.14159 * (radius_meters / 1000.0) ** 2)

            query = (
                select(
                    func.count(Ad.id).label('ad_count'),
                    func.avg(Ad.price_value).label('avg_price'),
                    func.avg(Ad.price_per_m2).label('avg_price_per_m2')
                )
                .where(Ad.location_point.isnot(None))
                .where(Ad.status == 'active')
                .where(
                    geo_func.ST_DWithin(
                        func.cast(Ad.location_point, Geometry),
                        func.cast(point, Geometry),
                        radius_meters
                    )
                )
            )

            result = session.execute(query).first()

            if result:
                ad_count = result[0]
                return {
                    'ad_count': ad_count,
                    'area_km2': area_km2,
                    'density_per_km2': ad_count / area_km2 if area_km2 > 0 else 0,
                    'avg_price': int(result[1]) if result[1] else None,
                    'avg_price_per_m2': int(result[2]) if result[2] else None
                }

            return {
                'ad_count': 0,
                'area_km2': area_km2,
                'density_per_km2': 0,
                'avg_price': None,
                'avg_price_per_m2': None
            }

    def get_city_statistics(self, city_name: str) -> Dict[str, Any]:
        """Get statistics for a city"""
        with self.get_session() as session:
            query = (
                select(
                    City.id,
                    City.name,
                    func.count(Ad.id).label('ad_count'),
                    func.avg(Ad.price_value).label('avg_price'),
                    func.avg(Ad.price_per_m2).label('avg_price_per_m2'),
                    func.min(Ad.price_value).label('min_price'),
                    func.max(Ad.price_value).label('max_price'),
                    func.avg(Ad.area_value).label('avg_area')
                )
                .outerjoin(Ad, City.id == Ad.city_id)
                .where(City.name.ilike(f'%{city_name}%'))
                .where(or_(Ad.status == 'active', Ad.status.is_(None)))
                .group_by(City.id, City.name)
            )

            result = session.execute(query).first()

            if result:
                return {
                    'city_id': result[0],
                    'city_name': result[1],
                    'ad_count': result[2],
                    'avg_price': float(result[3]) if result[3] else None,
                    'avg_price_per_m2': float(result[4]) if result[4] else None,
                    'min_price': result[5],
                    'max_price': result[6],
                    'avg_area': float(result[7]) if result[7] else None
                }

            return {}

    def search_ads(
        self,
        city_id: Optional[str] = None,
        district_id: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        rooms: Optional[int] = None,
        property_type: Optional[str] = None,
        features: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Ad]:
        """
        Advanced search with multiple filters.

        Args:
            city_id: Filter by city ID
            district_id: Filter by district ID
            min_price: Minimum price
            max_price: Maximum price
            min_area: Minimum area
            max_area: Maximum area
            rooms: Number of rooms
            property_type: Type of property
            features: List of required features
            limit: Maximum number of results

        Returns:
            List of Ad objects
        """
        with self.get_session() as session:
            query = select(Ad).where(Ad.status == 'active')

            # Apply filters
            if city_id:
                query = query.where(Ad.city_id == city_id)
            if district_id:
                query = query.where(Ad.district_id == district_id)
            if min_price:
                query = query.where(Ad.price_value >= min_price)
            if max_price:
                query = query.where(Ad.price_value <= max_price)
            if min_area:
                query = query.where(Ad.area_value >= min_area)
            if max_area:
                query = query.where(Ad.area_value <= max_area)
            if rooms:
                query = query.where(Ad.flat_number_of_rooms == rooms)
            if property_type:
                query = query.where(Ad.property_type == property_type)

            # Filter by features
            if features:
                for feature in features:
                    subq = (
                        select(AdFeature.ad_id)
                        .where(AdFeature.feature == feature)
                    )
                    query = query.where(Ad.id.in_(subq))

            query = query.order_by(Ad.price_value).limit(limit)

            return list(session.execute(query).scalars())


if __name__ == '__main__':
    # Example usage
    import os
    from dotenv import load_dotenv

    load_dotenv()

    conn_string = os.getenv(
        'DATABASE_URL',
        'postgresql://otodom_user:password123@localhost:5432/otodom_db'
    )

    db = DatabaseManager(conn_string)

    # Create all tables (run only once)
    # db.create_all_tables()

    print("DatabaseManager ready to use!")
