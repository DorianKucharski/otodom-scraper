import logging
import os
import sys
from dotenv import load_dotenv

from ad_scraper import Scraper
from parser import OtodomParser
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
        scraper = Scraper()
        raw_data = scraper.scrape(url)
        logger.info("Successfully scraped page")

        parser = OtodomParser()
        ad_dataclass = parser.parse(raw_data)
        logger.info(f"Parsed ad: {ad_dataclass.title}")

        with db_manager.get_session() as session:
            ad_model = Ad.from_dataclass(ad_dataclass, session)
            logger.info(f"Saved ad to database with ID: {ad_model.id}")

        return ad_dataclass

    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        raise


def example_queries(db_manager: DatabaseManager):
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE QUERIES")
    logger.info("="*80 + "\n")

    logger.info("1. Ads sorted by number of features (top 5):")
    ads_by_features = db_manager.get_ads_sorted_by_feature_count(limit=5)
    for ad in ads_by_features:
        logger.info(
            f"  - {ad['title'][:50]}... | "
            f"Features: {ad['features_count']}, "
            f"Equipment: {ad['equipment_count']}, "
            f"Price: {ad['price_value']:,} PLN"
        )

    logger.info("\n2. City statistics for Lublin:")
    stats = db_manager.get_city_statistics('Lublin')
    if stats:
        logger.info(f"  - Total ads: {stats['ad_count']}")
        logger.info(f"  - Average price: {stats['avg_price']:,.0f} PLN" if stats['avg_price'] else "  - Average price: N/A")
        logger.info(f"  - Average price/m²: {stats['avg_price_per_m2']:,.0f} PLN" if stats['avg_price_per_m2'] else "  - Average price/m²: N/A")
        logger.info(f"  - Price range: {stats['min_price']:,} - {stats['max_price']:,} PLN")

    logger.info("\n3. Ads within 1km radius from center of Lublin (51.2465, 22.5684):")
    nearby_ads = db_manager.get_ads_within_radius(
        latitude=51.2465,
        longitude=22.5684,
        radius_meters=1000,
        limit=5
    )
    for ad in nearby_ads:
        logger.info(
            f"  - {ad['title'][:40]}... | "
            f"Distance: {ad['distance_meters']:.0f}m, "
            f"Price: {ad['price_value']:,} PLN"
        )

    logger.info("\n4. Ad density in 2km radius from center of Lublin:")
    density = db_manager.get_ad_density_stats(
        latitude=51.2465,
        longitude=22.5684,
        radius_meters=2000
    )
    if density:
        logger.info(f"  - Total ads in area: {density['ad_count']}")
        logger.info(f"  - Area: {density['area_km2']:.2f} km²")
        logger.info(f"  - Density: {density['density_per_km2']:.2f} ads/km²")
        logger.info(f"  - Average price: {density['avg_price']:,} PLN" if density['avg_price'] else "  - Average price: N/A")

    logger.info("\n" + "="*80 + "\n")


def main():
    load_dotenv()

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL not found in environment variables")
        logger.error("Please create a .env file with DATABASE_URL or set it as environment variable")
        logger.error("Example: DATABASE_URL=postgresql://user:password@localhost:5432/otodom_db")
        sys.exit(1)

    db_manager = DatabaseManager(db_url)

    try:
        test_url = "https://www.otodom.pl/pl/oferta/rezerwacja-mieszkanie-wysoki-standard-blisko-uczelni-medycznej-ID4znz8"

        logger.info("Starting to scrape ad...")
        ad = scrape_and_save_ad(test_url, db_manager)

        logger.info(f"\nSuccessfully processed ad:")
        logger.info(f"  Title: {ad.title}")
        logger.info(f"  Price: {ad.price.value:,} PLN ({ad.price.per_m2:,} PLN/m²)")
        logger.info(f"  Location: {ad.location.address.city.name if ad.location.address.city else 'N/A'}")
        logger.info(f"  Area: {ad.property.area.value} {ad.property.area.unit}")
        logger.info(f"  Rooms: {ad.property.flat_properties.number_of_rooms}")

        example_queries(db_manager)

    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        db_manager.close()
        logger.info("Database connection closed")


def scrape_multiple_urls(urls: list[str], db_manager: DatabaseManager):
    successful = 0
    failed = 0

    for i, url in enumerate(urls, 1):
        logger.info(f"\nProcessing ad {i}/{len(urls)}")
        try:
            scrape_and_save_ad(url, db_manager)
            successful += 1
        except Exception as e:
            logger.error(f"Failed to process {url}: {e}")
            failed += 1
            continue

    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY: Successfully processed {successful}/{len(urls)} ads ({failed} failed)")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()
