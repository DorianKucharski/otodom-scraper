import logging
import sys

from data.ad_dto import AdDto
from otodom_scraper import OtodomScraper
from data.search_url import SearchUrl, OfferType, ObjectType, Location
from database import DatabaseManager
from data.models import Ad, County, Province, City, District, Owner
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ScrappingContext:
    database_manager: DatabaseManager

    existing_ad_ids: set[int]
    existing_owner_ids: set[int]
    existing_province_ids: set[str]
    existing_county_ids: set[str]
    existing_city_ids: set[int]
    existing_district_ids: set[int]

    def __init__(self, database_manager: DatabaseManager):
        self.database_manager = database_manager
        with database_manager.get_session() as session:
            self.existing_ad_ids = {a.id for a in session.query(Ad.id).all()}
            self.existing_owner_ids = {o.id for o in session.query(Owner.id).all()}
            self.existing_province_ids = {p.id for p in session.query(Province.id).all()}
            self.existing_county_ids = {c.id for c in session.query(County.id).all()}
            self.existing_city_ids = {c.id for c in session.query(City.id).all()}
            self.existing_district_ids = {d.id for d in session.query(District.id).all()}

    @staticmethod
    def _ensure_entity(session, cache: set, entity_id, factory):
        if entity_id is None:
            return
        if entity_id not in cache:
            session.merge(factory())
            session.flush()
            cache.add(entity_id)

    def process_ad(self, ad: AdDto):
        if ad.id in self.existing_ad_ids:
            logger.info(f"Ad with ID {ad.id} already exists, skipping...")
            return

        try:
            with self.database_manager.get_session() as session:
                self._ensure_entity(
                    session, self.existing_owner_ids, ad.owner.id, lambda: Owner.from_dataclass(ad.owner))

                self._ensure_entity(session, self.existing_province_ids, ad.location.address.province.id,
                                    lambda: Province.from_dataclass(ad.location.address.province))

                self._ensure_entity(session, self.existing_county_ids, ad.location.address.county.id,
                                    lambda: County.from_dataclass(ad.location.address.county))

                self._ensure_entity(session, self.existing_city_ids, ad.location.address.city.id,
                                    lambda: City.from_dataclass(ad.location.address.city))

                district_id = ad.location.address.district.id if ad.location.address.district else None
                self._ensure_entity(session, self.existing_district_ids, district_id,
                                    lambda: District.from_dataclass(ad.location.address.district))

                ad_model = Ad.from_dataclass(ad)
                session.merge(ad_model)

                self.existing_ad_ids.add(ad.id)
                logger.info(f"Saved ad with ID: {ad.id}")

        except Exception as e:
            logger.error(f"Error processing ad: {e}")
            raise


def main():
    scraper = OtodomScraper()
    db_manager = DatabaseManager()
    scrapping_context = ScrappingContext(db_manager)

    urls = [
        SearchUrl(
            offer_type=OfferType.SALE,
            object_type=ObjectType.HOUSE,
            location=Location(
                voivodeship="lubelskie",
                city="lublin",
            ),
            price_to=1000000,
        ),
        # SearchUrl(
        #     offer_type=OfferType.SALE,
        #     object_type=ObjectType.APARTMENT,
        #     location=Location(
        #         voivodeship="lubelskie",
        #         city="lublin",
        #     ),
        #     price_to=1000000,
        # ),
    ]

    for url in urls:
        page_number = 1
        while True:
            url.page_number = page_number
            search_result = scraper.scrape_search(url.build())
            for ad_item in search_result.items:
                scraped_ad = scraper.scrape_ad(ad_item.url)
                scrapping_context.process_ad(scraped_ad)

            if page_number >= search_result.total_pages:
                break
            page_number += 1


def drop_tables():
    db_manager = DatabaseManager()
    db_manager.drop_all_tables()


def create_tables():
    db_manager = DatabaseManager()
    db_manager.create_all_tables()


if __name__ == '__main__':
    main()
