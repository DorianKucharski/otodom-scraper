import logging
from dataclasses import dataclass
from time import sleep
from typing import Optional

import typer
from data.ad_dto import AdDto
from data.models import Ad, County, Province, City, District, Owner
from data.search_url import SearchUrl, OfferType, ObjectType, Location
from database import DatabaseManager
from otodom_scraper import OtodomScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ScrappingContext:
    existing_ad_ids: set[int]
    existing_ad_urls: list[str]
    existing_owner_ids: set[int]
    existing_province_ids: set[str]
    existing_county_ids: set[str]
    existing_city_ids: set[int]
    existing_district_ids: set[int]

    def __init__(self, database_manager: DatabaseManager, scraper: OtodomScraper):
        self.__database_manager = database_manager
        self.__scraper = scraper
        with database_manager.get_session() as session:
            self.existing_ad_ids = {a.id for a in session.query(Ad.id).all()}
            self.existing_ad_urls = [
                a.url for a in session.query(Ad.url)
                .order_by(Ad.modified_at.asc())
                .all()
            ]
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

    @staticmethod
    def with_retry(func: callable, *args, max_tries: int = 3, **kwargs):
        exception = None
        for try_number in range(max_tries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                exception = e
                logger.error(f"Error calling {func.__name__} - {try_number} of {max_tries} tries - {e}")
                sleep(10)
        raise exception

    def scrape_ad(self, url: str):
        return self.with_retry(self.__scrape_ad, url)

    def update_ad(self, ad: AdDto):
        return self.with_retry(self.__update_ad, ad)

    def __scrape_ad(self, url: str):
        if url is None or url == "":
            return

        if url in self.existing_ad_urls:
            logger.info(f"URL {url} already exists, skipping...")
            return

        ad: AdDto = self.__scraper.scrape_ad(url)
        if ad.id in self.existing_ad_ids:
            logger.info(f"Ad with ID {ad.id} already exists, skipping...")
            return

        try:
            with self.__database_manager.get_session() as session:
                self._ensure_entity(
                    session,
                    self.existing_owner_ids,
                    ad.owner.id,
                    lambda: Owner.from_dataclass(ad.owner)
                )

                self._ensure_entity(
                    session,
                    self.existing_province_ids,
                    ad.location.address.province.id,
                    lambda: Province.from_dataclass(ad.location.address.province)
                )

                self._ensure_entity(
                    session,
                    self.existing_county_ids,
                    ad.location.address.county.id,
                    lambda: County.from_dataclass(ad.location.address.county)
                )

                self._ensure_entity(
                    session,
                    self.existing_city_ids,
                    ad.location.address.city.id,
                    lambda: City.from_dataclass(ad.location.address.city)
                )

                if ad.location.address.district:
                    self._ensure_entity(
                        session,
                        self.existing_district_ids,
                        ad.location.address.district.id,
                        lambda: District.from_dataclass(ad.location.address.district)
                    )

                ad_model = Ad.from_dataclass(ad)
                session.merge(ad_model)

                self.existing_ad_ids.add(ad.id)
                logger.info(f"Saved ad with ID: {ad.id}")

        except Exception as e:
            logger.error(f"Error processing ad: {ad.url} - {e}")
            raise

    def __update_ad(self, ad_dto: AdDto):
        with self.__database_manager.get_session() as session:
            ad = session.query(Ad).filter(Ad.id == ad_dto.id).first()
            if ad is None:
                raise ValueError(f"Ad with id {ad_dto.id} not found")
            ad.update_status(ad_dto.status)



def scrape(urls: list[SearchUrl]):
    scraper = OtodomScraper()
    db_manager = DatabaseManager()
    scrapping_context = ScrappingContext(db_manager, scraper)
    db_manager.create_all_tables()

    for url in urls:
        page_number = 1
        while True:
            url.page_number = page_number
            search_result = scraper.scrape_search(url.build())
            for ad_item in search_result.items:
                scrapping_context.scrape_ad(ad_item.url)

            if page_number >= search_result.total_pages:
                break
            page_number += 1

    for url in scrapping_context.existing_ad_urls:
        ad = scraper.scrape_ad(url)
        scrapping_context.update_ad(ad)


def drop_tables():
    db_manager = DatabaseManager()
    db_manager.drop_all_tables()

def build_urls(
        houses: bool,
        apartments: bool,
        sale: bool,
        rent: bool,
        location: Optional[Location] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
) -> list[SearchUrl]:
    object_types = []
    if houses:
        object_types.append(ObjectType.HOUSE)
    if apartments:
        object_types.append(ObjectType.APARTMENT)

    offer_types = []
    if sale:
        offer_types.append(OfferType.SALE)
    if rent:
        offer_types.append(OfferType.RENT)

    return [
        SearchUrl(
            offer_type=offer_type,
            object_type=object_type,
            location=location,
            price_from=price_from,
            price_to=price_to,
        )
        for offer_type in offer_types
        for object_type in object_types
        if not (object_type == ObjectType.INVESTMENT and offer_type == OfferType.RENT)
        if not (object_type == ObjectType.ROOM and offer_type == OfferType.SALE)
    ]

def main(
        houses: bool = typer.Option(True, '--houses/--no-houses'),
        apartments: bool = typer.Option(True, '--apartments/--no-apartments'),
        sale: bool = typer.Option(True, '--sale/--no-sale'),
        rent: bool = typer.Option(True, '--rent/--no-rent'),
        voivodeship: str = typer.Option(None, '--voivodeship'),
        city: str = typer.Option(None, '--city'),
        district: str = typer.Option(None, '--district'),
        min_price: int = typer.Option(0, '--min-price'),
        max_price: int = typer.Option(1000000, '--max-price'),
):
    if district and not city:
        raise typer.BadParameter("--district requires --city")
    if city and not voivodeship:
        raise typer.BadParameter("--city requires --voivodeship")
    location = Location(
        voivodeship=voivodeship,
        city=city,
        district=district
    ) if voivodeship else None

    urls = build_urls(
        houses=houses,
        apartments=apartments,
        sale=sale,
        rent=rent,
        location=location,
        price_from=min_price if min_price else None,
        price_to=max_price if max_price else None,
    )

    scrape(urls)

if __name__ == '__main__':
    typer.run(main)
