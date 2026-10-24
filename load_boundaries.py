import logging
import sys

import typer

from data.admin_areas import load_admin_areas
from database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    with database_manager.engine.begin() as connection:
        counts = load_admin_areas(connection)
    logger.info("Admin areas replaced: %s", counts)


if __name__ == "__main__":
    typer.run(main)
