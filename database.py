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

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, connection_string: str, echo: bool = False):
        self.engine = create_engine(connection_string, echo=echo)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("Database connection initialized with SQLAlchemy")

    def create_all_tables(self):
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            logger.info("PostgreSQL extensions created")

        Base.metadata.create_all(self.engine)
        logger.info("All tables created successfully")

    def drop_all_tables(self):
        Base.metadata.drop_all(self.engine)
        logger.warning("All tables dropped")

    @contextmanager
    def get_session(self):
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

    def get_ad_by_id(self, ad_id: int) -> Optional[Ad]:
        with self.get_session() as session:
            return session.get(Ad, ad_id)

    def get_ads_by_city(
        self,
        city_name: str,
        limit: int = 100,
        status: str = 'active'
    ) -> List[Ad]:
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
        with self.get_session() as session:
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
        with self.get_session() as session:
            point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)

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
        with self.get_session() as session:
            query = select(Ad).where(Ad.status == 'active')

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
    import os
    from dotenv import load_dotenv

    load_dotenv()

    conn_string = os.getenv(
        'DATABASE_URL',
        'postgresql://otodom_user:password123@localhost:5432/otodom_db'
    )

    db = DatabaseManager(conn_string)

    print("DatabaseManager ready to use!")
