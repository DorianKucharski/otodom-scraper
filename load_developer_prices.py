import logging
import sys

import typer

from data.developer_price_lists import refresh_developer_prices
from database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main(
        cities: list[str] = typer.Option(
            ["Kraków"], "--city", help="Keep developer price lists around this city (repeatable). "
                                       "Needs load_boundaries.py first."
        ),
        margin_km: float = typer.Option(15, "--margin-km", help="How far beyond the city boundary to keep."),
):
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    stored = refresh_developer_prices(database_manager.engine, cities, int(margin_km * 1000))
    logger.info("Stored %d new developer units around %s", stored, ", ".join(cities))


if __name__ == "__main__":
    typer.run(main)
