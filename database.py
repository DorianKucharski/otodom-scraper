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
