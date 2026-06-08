import logging
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


class ScrapingContext:
    existing_ad_ids: set[int]
    existing_ad_urls: set[str]
    existing_owner_ids: set[int]
    existing_province_ids: set[str]
    existing_county_ids: set[str]
    existing_city_ids: set[int]
    existing_district_ids: set[int]

    def __init__(
            self,
            database_manager: DatabaseManager,
            scraper: OtodomScraper,
            update_if_older_than_days: Optional[int] = 30
    ):
        self.__database_manager = database_manager
        self.__scraper = scraper
        self.__update_if_older_than_days = update_if_older_than_days

        with database_manager.get_session() as session:
            self.existing_ad_ids = {a.id for a in session.query(Ad.id).all()}
            self.existing_ad_urls = {
                a.url for a in session.query(Ad.url)
                .order_by(Ad.modified_at.asc())
                .all()
            }
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

    def scrape_ad(self, url: str, offer_type: OfferType, object_type: ObjectType):
        return self.with_retry(self.__scrape_ad, url, offer_type.name, object_type.name)

    def __scrape_ad(self, url: str, offer_type: str, object_type: str):
        is_update_enabled: bool = self.__update_if_older_than_days is not None

        if url is None or url == "":
            return

        if url in self.existing_ad_urls:
            if is_update_enabled:
                with self.__database_manager.get_session() as session:
                    saved_ad = session.query(Ad).filter(Ad.url == url).first()
                    if saved_ad is None:
                        logger.warning(f"URL {url} found in cache but not in DB")
                        return
                    if saved_ad.should_update(self.__update_if_older_than_days):
                        logger.info(f"Updating ad with url: {url} - last update was at - {saved_ad.modified_at}")
                        ad_dto: AdDto = self.__scraper.scrape_ad(url)
                        if ad_dto:
                            saved_ad.update(ad_dto, offer_type, object_type)
                        else:
                            logger.warning(f"URL {url} could not be scraped")
                    else:
                        logger.info(f"Skipping update of url: {url} - last update was at - {saved_ad.modified_at}")
            else:
                logger.info(f"URL {url} already exists, skipping...")
            return

        ad_dto: AdDto = self.__scraper.scrape_ad(url)
        if ad_dto:
            if ad_dto.id in self.existing_ad_ids:
                with self.__database_manager.get_session() as session:
                    saved_ad = session.query(Ad).filter(Ad.id == ad_dto.id).first()

                    if saved_ad is not None:
                        saved_ad.update(ad_dto, offer_type, object_type)
                        self.existing_ad_urls.add(ad_dto.url)
                        logger.info(f"Updating ad - id: {ad_dto.id} - url: {ad_dto.url}")
                        return

                logger.warning(f"Ad id {ad_dto.id} found in cache but not in DB")
                self.__save_new_ad(ad_dto, offer_type, object_type)
                self.existing_ad_ids.add(ad_dto.id)
                self.existing_ad_urls.add(ad_dto.url)
                logger.info(f"Saved ad with ID: {ad_dto.id} - url: {ad_dto.url}")
            else:
                self.__save_new_ad(ad_dto, offer_type, object_type)
                self.existing_ad_ids.add(ad_dto.id)
                self.existing_ad_urls.add(ad_dto.url)
                logger.info(f"Saved ad with ID: {ad_dto.id} - url: {ad_dto.url}")
        else:
            logger.warning(f"URL {url} could not be scraped")

    def __save_new_ad(self, ad: AdDto, offer_type: str, object_type: str):
        try:
            with self.__database_manager.get_session() as session:
                if ad.owner:
                    self._ensure_entity(
                        session,
                        self.existing_owner_ids,
                        ad.owner.id,
                        lambda: Owner.from_dataclass(ad.owner)
                    )

                address = ad.location.address if ad.location else None

                if address and address.province:
                    self._ensure_entity(
                        session,
                        self.existing_province_ids,
                        address.province.id,
                        lambda: Province.from_dataclass(address.province)
                    )

                if address and address.county:
                    self._ensure_entity(
                        session,
                        self.existing_county_ids,
                        address.county.id,
                        lambda: County.from_dataclass(address.county)
                    )

                if address and address.city:
                    self._ensure_entity(
                        session,
                        self.existing_city_ids,
                        address.city.id,
                        lambda: City.from_dataclass(address.city)
                    )

                if address and address.district:
                    self._ensure_entity(
                        session,
                        self.existing_district_ids,
                        address.district.id,
                        lambda: District.from_dataclass(address.district)
                    )

                ad_model = Ad.from_dataclass(ad, offer_type, object_type)
                session.merge(ad_model)
        except Exception as e:
            logger.error(f"Error processing ad: {ad.url} - {e}")
            raise

    def update_existing_ads(
            self,
            city: Optional[str] = None,
            min_price: Optional[int] = None,
            max_price: Optional[int] = None,
            object_types: Optional[list[str]] = None,
            offer_types: Optional[list[str]] = None,
    ):
        """Re-scrape ads already stored in the DB and refresh them (status, price, ...).

        Used to detect listings that are no longer active - the scraper still returns
        the ad's status, so Ad.update() picks up the change.
        """
        with self.__database_manager.get_session() as session:
            query = session.query(Ad.id)
            if city:
                query = query.join(Ad.city).filter(City.name.ilike(city))
            if min_price is not None:
                query = query.filter(Ad.price_value >= min_price)
            if max_price is not None:
                query = query.filter(Ad.price_value <= max_price)
            # TODO: enable once offer_type/object_type are populated in the DB
            # if object_types:
            #     query = query.filter(Ad.object_type.in_(object_types))
            # if offer_types:
            #     query = query.filter(Ad.offer_type.in_(offer_types))
            # Start from the stalest ads first
            query = query.order_by(Ad.modified_at.asc())
            ad_ids = [row.id for row in query.all()]

        logger.info(f"Found {len(ad_ids)} ads in DB to verify")
        for ad_id in ad_ids:
            self.update_existing_ad(ad_id)

    def update_existing_ad(self, ad_id: int):
        return self.with_retry(self.__update_existing_ad, ad_id)

    def __update_existing_ad(self, ad_id: int):
        with self.__database_manager.get_session() as session:
            saved_ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if saved_ad is None:
                return

            url = saved_ad.url
            ad_dto: AdDto = self.__scraper.scrape_ad(url)
            if ad_dto is None:
                logger.warning(f"Ad {ad_id} could not be scraped - url: {url}")
                return

            # Preserve offer_type/object_type - they are not part of the scraped JSON
            saved_ad.update(ad_dto, saved_ad.offer_type, saved_ad.object_type)
            logger.info(f"Updated ad {ad_id} - status: {ad_dto.status} - url: {url}")


def scrape(urls: list[SearchUrl]):
    scraper = OtodomScraper()
    db_manager = DatabaseManager()
    db_manager.create_all_tables()
    scraping_context = ScrapingContext(db_manager, scraper)

    for url in urls:
        page_number = 1
        while True:
            url.page_number = page_number
            search_result = scraper.scrape_search(url.build())
            for ad_item in search_result.items:
                scraping_context.scrape_ad(ad_item.url, url.offer_type, url.object_type)

            if page_number >= search_result.total_pages:
                break
            page_number += 1


def update_ads(
        city: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        object_types: Optional[list[ObjectType]] = None,
        offer_types: Optional[list[OfferType]] = None,
):
    scraper = OtodomScraper()
    db_manager = DatabaseManager()
    db_manager.create_all_tables()
    scraping_context = ScrapingContext(db_manager, scraper)

    scraping_context.update_existing_ads(
        city=city,
        min_price=min_price,
        max_price=max_price,
        object_types=[o.name for o in object_types] if object_types else None,
        offer_types=[o.name for o in offer_types] if offer_types else None,
    )


def drop_tables():
    db_manager = DatabaseManager()
    db_manager.drop_all_tables()


def build_object_types(houses: bool, apartments: bool) -> list[ObjectType]:
    object_types = []
    if houses:
        object_types.append(ObjectType.HOUSE)
    if apartments:
        object_types.append(ObjectType.APARTMENT)
    return object_types


def build_offer_types(sale: bool, rent: bool) -> list[OfferType]:
    offer_types = []
    if sale:
        offer_types.append(OfferType.SALE)
    if rent:
        offer_types.append(OfferType.RENT)
    return offer_types


def build_urls(
        houses: bool,
        apartments: bool,
        sale: bool,
        rent: bool,
        location: Optional[Location] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
) -> list[SearchUrl]:
    object_types = build_object_types(houses, apartments)
    offer_types = build_offer_types(sale, rent)

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
        scrape_enabled: bool = typer.Option(
            True, '--scrape/--no-scrape',
            help="Scrape search results to discover and save new ads."
        ),
        update_enabled: bool = typer.Option(
            True, '--update/--no-update',
            help="Re-scrape ads already in the DB to refresh their status."
        ),
):
    if district and not city:
        raise typer.BadParameter("--district requires --city")
    if city and not voivodeship:
        raise typer.BadParameter("--city requires --voivodeship")
    if not scrape_enabled and not update_enabled:
        raise typer.BadParameter("At least one of --scrape / --update must be enabled")

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

    while True:
        if scrape_enabled:
            scrape(urls)
            logger.info("All listings have been scraped.")

        if update_enabled:
            update_ads(
                city=city,
                min_price=min_price if min_price else None,
                max_price=max_price if max_price else None,
                object_types=build_object_types(houses, apartments),
                offer_types=build_offer_types(sale, rent),
            )
            logger.info("All existing ads have been verified.")

        logger.info("Cycle complete. Restarting in 60 seconds...")
        sleep(60)


if __name__ == '__main__':
    typer.run(main)
