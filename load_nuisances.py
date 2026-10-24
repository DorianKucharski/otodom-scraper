import logging
import sys

import typer

from data.nuisances import load_nuisances
from database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main(
        cities: list[str] = typer.Option(
            ["Kraków"], "--city", help="Load roads, railways and runways around this city (repeatable). "
                                       "Needs load_boundaries.py first."
        ),
        margin_km: float = typer.Option(15, "--margin-km", help="How far beyond the city boundary to load."),
):
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    loaded = load_nuisances(database_manager.engine, cities, int(margin_km * 1000))
    logger.info("Loaded %d OpenStreetMap roads, railways and runways around %s", loaded, ", ".join(cities))


if __name__ == "__main__":
    typer.run(main)
