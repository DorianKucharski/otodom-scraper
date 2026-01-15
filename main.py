"""
Otodom Scraper - Main Application
Scrapes real estate ads from Otodom.pl and stores them in PostgreSQL database.
"""

import logging
import os
import sys
from dotenv import load_dotenv

from scraper import Scraper
from parser import OtodomParser
from database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scrape_and_save_ad(url: str, db_manager: DatabaseManager):
    """
    Scrape a single ad and save it to database.

    Args:
        url: Otodom ad URL
        db_manager: Database manager instance
    """
    logger.info(f"Scraping URL: {url}")

    try:
        # Scrape the page
        scraper = Scraper()
        raw_data = scraper.scrape(url)
        logger.info("Successfully scraped page")

        # Parse the data
        parser = OtodomParser()
        ad = parser.parse(raw_data)
        logger.info(f"Parsed ad: {ad.title}")

        # Save to database
        ad_id = db_manager.save_ad(ad)
        logger.info(f"Saved ad to database with ID: {ad_id}")

        return ad

    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        raise


def example_queries(db_manager: DatabaseManager):
    """
    Demonstrate advanced query capabilities.

    Args:
        db_manager: Database manager instance
    """
    logger.info("\n" + "="*80)
    logger.info("EXAMPLE QUERIES")
    logger.info("="*80 + "\n")

    # Example 1: Get ads sorted by feature count
    logger.info("1. Ads sorted by number of features (top 5):")
    ads_by_features = db_manager.get_ads_sorted_by_feature_count(limit=5)
    for ad in ads_by_features:
        logger.info(
            f"  - {ad['title'][:50]}... | "
            f"Features: {ad['features_count']}, "
            f"Equipment: {ad['equipment_count']}, "
            f"Price: {ad['price_value']:,} PLN"
        )

    # Example 2: Get city statistics
    logger.info("\n2. City statistics for Lublin:")
    stats = db_manager.get_city_statistics('Lublin')
    if stats:
        logger.info(f"  - Total ads: {stats['ad_count']}")
        logger.info(f"  - Average price: {stats['avg_price']:,.0f} PLN" if stats['avg_price'] else "  - Average price: N/A")
        logger.info(f"  - Average price/m²: {stats['avg_price_per_m2']:,.0f} PLN" if stats['avg_price_per_m2'] else "  - Average price/m²: N/A")
        logger.info(f"  - Price range: {stats['min_price']:,} - {stats['max_price']:,} PLN")

    # Example 3: Get ads within radius (if coordinates available)
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

    # Example 4: Get density statistics
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
    """Main application entry point."""
    # Load environment variables from .env file
    load_dotenv()

    # Get database connection string
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL not found in environment variables")
        logger.error("Please create a .env file with DATABASE_URL or set it as environment variable")
        logger.error("Example: DATABASE_URL=postgresql://user:password@localhost:5432/otodom_db")
        sys.exit(1)

    # Initialize database manager
    db_manager = DatabaseManager(db_url)

    try:
        # Optional: Initialize schema (run only once or when updating schema)
        # Uncomment the following lines to initialize/update database schema:
        # logger.info("Creating all tables...")
        # db_manager.create_all_tables()
        # logger.info("Database schema initialized successfully")

        # Example: Scrape and save an ad
        test_url = "https://www.otodom.pl/pl/oferta/rezerwacja-mieszkanie-wysoki-standard-blisko-uczelni-medycznej-ID4znz8"

        logger.info("Starting to scrape ad...")
        ad = scrape_and_save_ad(test_url, db_manager)

        logger.info(f"\nSuccessfully processed ad:")
        logger.info(f"  Title: {ad.title}")
        logger.info(f"  Price: {ad.price.value:,} PLN ({ad.price.per_m2:,} PLN/m²)")
        logger.info(f"  Location: {ad.location.address.city.name if ad.location.address.city else 'N/A'}")
        logger.info(f"  Area: {ad.property.area.value} {ad.property.area.unit}")
        logger.info(f"  Rooms: {ad.property.flat_properties.number_of_rooms}")

        # Run example queries to demonstrate database capabilities
        example_queries(db_manager)

    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)
    finally:
        db_manager.close()
        logger.info("Database connection closed")


def scrape_multiple_urls(urls: list[str], db_manager: DatabaseManager):
    """
    Scrape multiple URLs and save them to database.

    Args:
        urls: List of Otodom URLs
        db_manager: Database manager instance
    """
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
    """
    Example usage:

    1. Create a .env file with your database credentials:
       DATABASE_URL=postgresql://user:password@localhost:5432/otodom_db

    2. Install dependencies:
       pip install -r requirements.txt

    3. Create PostgreSQL database and run migrations:
       psql -U postgres -c "CREATE DATABASE otodom_db;"

       # Option A: Use Alembic migrations (recommended)
       alembic upgrade head

       # Option B: Create tables directly from models
       # Uncomment db_manager.create_all_tables() in main()

    4. Run the scraper:
       python main.py

    Advanced usage:
    - Scrape multiple URLs:
      urls = [
          "https://www.otodom.pl/pl/oferta/...",
          "https://www.otodom.pl/pl/oferta/...",
      ]
      scrape_multiple_urls(urls, db_manager)

    - Query database:
      Use db_manager methods to query:
      - get_ads_by_city()
      - get_ads_sorted_by_feature_count()
      - get_ads_within_radius()
      - get_ad_density_stats()
      - get_city_statistics()

    - Build custom queries:
      Use psql or any PostgreSQL client to query the database directly.
      Check schema.sql for available views and functions.
    """
    main()
