import logging
import sys

import typer

from data.nuisances import features_from_overpass, overpass_query, store_nuisances
from data.overpass import area_bounds, fetch
from data.street_checks import overpass_streets_query, store_streets, streets_from_overpass
from database import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main(
        cities: list[str] = typer.Option(
            ["Kraków"], "--city", help="Load OpenStreetMap context around this city (repeatable). "
                                       "Needs load_boundaries.py first."
        ),
        margin_km: float = typer.Option(15, "--margin-km", help="How far beyond the city boundary to load."),
):
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    bounds = area_bounds(database_manager.engine, cities, int(margin_km * 1000))
    nuisances = store_nuisances(database_manager.engine, features_from_overpass(fetch(overpass_query(*bounds))))
    logger.info("Loaded %d roads, railways and runways around %s", nuisances, ", ".join(cities))
    streets = store_streets(database_manager.engine, streets_from_overpass(fetch(overpass_streets_query(*bounds))))
    logger.info("Loaded %d named streets around %s", streets, ", ".join(cities))


if __name__ == "__main__":
    typer.run(main)
