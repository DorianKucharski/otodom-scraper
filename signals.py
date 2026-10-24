import logging
import sys

import typer

from data.market_signals import refresh_market_signals
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
    refresh_market_signals(database_manager.engine)


if __name__ == "__main__":
    typer.run(main)
