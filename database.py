import logging
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from data.models import (
    Base
)

logger = logging.getLogger(__name__)

DISTRICT_PRICE_STATS_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS district_price_stats AS
SELECT a.city_id,
       a.district_id,
       grouping(a.district_id)                                         AS is_city_level,
       a.offer_type,
       a.object_type,
       count(*)                                                        AS ad_count,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY a.price_per_m2)      AS median_price_per_m2,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY a.price_per_m2)     AS p25_price_per_m2,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY a.price_per_m2)     AS p75_price_per_m2,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY a.price_value)       AS median_price,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY a.area_value)        AS median_area
FROM ads a
WHERE a.status = 'active'
  AND a.price_per_m2 IS NOT NULL
  AND a.price_per_m2 > 0
GROUP BY GROUPING SETS (
    (a.city_id, a.district_id, a.offer_type, a.object_type),
    (a.city_id, a.offer_type, a.object_type)
)
"""

AD_ALL_FEATURES_VIEW = """
CREATE OR REPLACE VIEW ad_all_features AS
SELECT ad_id, 'feature' AS feature_group, feature AS value FROM ad_features
UNION ALL
SELECT ad_id, 'equipment', equipment FROM ad_flat_equipment
UNION ALL
SELECT ad_id, 'area', area FROM ad_flat_areas
UNION ALL
SELECT ad_id, 'parking', parking FROM ad_flat_parking
UNION ALL
SELECT ad_id, 'window', window_type FROM ad_building_windows
UNION ALL
SELECT ad_id, 'convenience', convenience FROM ad_building_conveniences
UNION ALL
SELECT ad_id, 'security', security FROM ad_building_security
"""

DISTRICT_PRICE_STATS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_district_price_stats_lookup
    ON district_price_stats (city_id, district_id, is_city_level, offer_type, object_type)
"""


class DatabaseManager:
    def __init__(self, echo: bool = False):
        load_dotenv()

        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.error("DATABASE_URL not found in environment variables")
            logger.error("Please create a .env file with DATABASE_URL or set it as environment variable")
            logger.error("Example: DATABASE_URL=postgresql://user:password@localhost:5432/otodom_db")
            raise Exception("Database connection failed")

        self.engine = create_engine(db_url, echo=echo)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("Database connection initialized with SQLAlchemy")

    def create_all_tables(self):
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            logger.info("PostgreSQL extensions created")

        Base.metadata.create_all(self.engine)
        logger.info("All tables created successfully")

        with self.engine.begin() as conn:
            conn.execute(text(AD_ALL_FEATURES_VIEW))
            conn.execute(text(DISTRICT_PRICE_STATS_VIEW))
            conn.execute(text(DISTRICT_PRICE_STATS_INDEX))
            logger.info("Read model views created")

    def refresh_district_price_stats(self):
        with self.engine.begin() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW district_price_stats"))
        logger.info("District price stats view refreshed")

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
