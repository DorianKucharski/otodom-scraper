import logging
import sys

import typer

from data.rcn import load_flat_sales
from database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main(
        cities: list[str] = typer.Option(
            ["Kraków"], "--city", help="Load flat sales around this city (repeatable). Needs load_boundaries.py first."
        ),
        margin_km: float = typer.Option(15, "--margin-km", help="How far beyond the city boundary to load."),
):
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    with database_manager.engine.begin() as connection:
        loaded = load_flat_sales(connection, cities, int(margin_km * 1000))
    logger.info("Loaded %d RCN flat sales around %s", loaded, ", ".join(cities))


if __name__ == "__main__":
    typer.run(main)
