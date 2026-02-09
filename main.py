import logging
import os
import sys
from dotenv import load_dotenv

from ad_scraper import AdScraper
from database import DatabaseManager
from models import Ad

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scrape_and_save_ad(url: str, db_manager: DatabaseManager):
    logger.info(f"Scraping URL: {url}")

    try:
        scraper = AdScraper()
        ad_dataclass = scraper.scrape(url)


        with db_manager.get_session() as session:
            ad_model = Ad.from_dataclass(ad_dataclass, session)
            logger.info(f"Saved ad to database with ID: {ad_model.id}")

        return ad_dataclass

    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        raise


def main():
    db_manager = DatabaseManager()
    # db_manager.drop_all_tables()
    db_manager.create_all_tables()

    try:
        test_url = "https://www.otodom.pl/pl/oferta/mieszkanie-lublin-45-4m2-2-pietro-2-pok-ID4zYrx"

        logger.info("Starting to scrape ad...")
        ad = scrape_and_save_ad(test_url, db_manager)

        logger.info(f"\nSuccessfully processed ad:")
        logger.info(f"  Title: {ad.title}")
        logger.info(f"  Price: {ad.price.value:,} PLN ({ad.price.per_m2:,} PLN/m²)")
        logger.info(f"  Location: {ad.location.address.city.name if ad.location.address.city else 'N/A'}")
        logger.info(f"  Area: {ad.property.area.value} {ad.property.area.unit}")
        logger.info(f"  Rooms: {ad.property.flat_properties.number_of_rooms}")

    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        # db_manager.close()
        logger.info("Database connection closed")




if __name__ == '__main__':
    main()
