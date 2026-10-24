import logging
import sys
from datetime import datetime, timedelta
from time import sleep
from typing import Optional

import typer
from sqlalchemy import func, or_

from data.ad_dto import AdDto
from data.location_resolver import LocationIndex, complete_location
from data.price_history import PriceState, price_observation, price_state_of
from data.raw_payload import raw_payload_row
from data.search_dto import SearchResultDto
from data.models import Ad, AdRawPayload, AdStatus, County, Province, City, District, Owner, ServiceStatus, is_masked
from data.search_url import SearchUrl, OfferType, ObjectType, Location
from database import DatabaseManager
from monitoring.heartbeat import ServiceHeartbeatWriter
from monitoring.log_handler import attach_database_logging
from monitoring.services import SCRAPER_SERVICE
from otodom_scraper import OtodomBlockedError, OtodomScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

FAILURE_PAUSE_SECONDS = 10
BLOCKED_PAUSE_SECONDS = 60
BLOCKED_MAX_PAUSE_SECONDS = 1800


class ScrapeRetry:
    def __init__(self, scraper: OtodomScraper, max_tries: int = 3, max_blocked_tries: int = 6):
        self.__scraper = scraper
        self.__max_tries = max_tries
        self.__max_blocked_tries = max_blocked_tries
        self.consecutive_blocks = 0

    def blocked_pause_seconds(self) -> int:
        exponent = min(self.consecutive_blocks - 1, 10)
        return min(BLOCKED_PAUSE_SECONDS * 2 ** exponent, BLOCKED_MAX_PAUSE_SECONDS)

    def __call__(self, func: callable, *args, **kwargs):
        failures = 0
        blocked_tries = 0
        while True:
            try:
                result = func(*args, **kwargs)
                self.consecutive_blocks = 0
                return result
            except OtodomBlockedError as e:
                self.consecutive_blocks += 1
                blocked_tries += 1
                pause = self.blocked_pause_seconds()
                logger.warning(
                    f"Blocked by otodom - {blocked_tries} of {self.__max_blocked_tries} tries - "
                    f"pausing {pause}s with a fresh session - {e}"
                )
                sleep(pause)
                self.__scraper.reset_session()
                if blocked_tries >= self.__max_blocked_tries:
                    raise
            except Exception as e:
                failures += 1
                logger.error(f"Error calling {func.__name__} - {failures} of {self.__max_tries} tries - {e}")
                if failures >= self.__max_tries:
                    raise
                sleep(FAILURE_PAUSE_SECONDS)


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
            update_if_older_than_days: Optional[int] = 30,
            store_raw_payloads: bool = True,
    ):
        self.__database_manager = database_manager
        self.__scraper = scraper
        self.__update_if_older_than_days = update_if_older_than_days
        self.__store_raw_payloads = store_raw_payloads
        self.with_retry = ScrapeRetry(scraper)

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
            self.location_index = self._load_location_index(session)

    @staticmethod
    def _load_location_index(session) -> LocationIndex:
        district_usage = (
            session.query(Ad.city_id, District.code, District.id, func.count(Ad.id))
            .join(District, District.id == Ad.district_id)
            .filter(Ad.city_id.is_not(None))
            .group_by(Ad.city_id, District.code, District.id)
            .all()
        )
        return LocationIndex.build(
            provinces=session.query(Province.id, Province.code).all(),
            counties=session.query(County.id, County.code).all(),
            city_ids=[row.id for row in session.query(City.id).all()],
            districts=session.query(District.id, District.code).all(),
            district_usage=district_usage,
        )

    def _fetch_ad(self, url: str) -> Optional[AdDto]:
        ad_dto = self.__scraper.scrape_ad(url)
        if ad_dto:
            complete_location(ad_dto, self.location_index)
        return ad_dto

    def _store_dimensions(self, session, ad: AdDto):
        if ad.owner:
            self._ensure_entity(session, self.existing_owner_ids, ad.owner.id, lambda: Owner.from_dataclass(ad.owner))

        address = ad.location.address if ad.location else None
        if address is None:
            return
        if address.province:
            self._ensure_entity(
                session, self.existing_province_ids, address.province.id,
                lambda: Province.from_dataclass(address.province),
            )
        if address.county:
            self._ensure_entity(
                session, self.existing_county_ids, address.county.id,
                lambda: County.from_dataclass(address.county),
            )
        if address.city:
            self._ensure_entity(
                session, self.existing_city_ids, address.city.id,
                lambda: City.from_dataclass(address.city),
            )
        if address.district:
            self._ensure_entity(
                session, self.existing_district_ids, address.district.id,
                lambda: District.from_dataclass(address.district),
            )

    def _store_raw_payload(self, session, ad: AdDto):
        if not self.__store_raw_payloads:
            return
        if is_masked(ad.description) and session.get(AdRawPayload, ad.id) is not None:
            return
        row = raw_payload_row(ad.id, ad.raw_payload, datetime.now())
        if row is not None:
            session.merge(row)

    @staticmethod
    def _record_price(session, ad: Ad, previous: Optional[PriceState]):
        observation = price_observation(ad, previous, datetime.now())
        if observation is not None:
            session.add(observation)

    def _refresh(self, session, saved_ad: Ad, ad_dto: AdDto, offer_type: Optional[str], object_type: Optional[str]):
        previous = price_state_of(saved_ad)
        self._store_dimensions(session, ad_dto)
        saved_ad.update(ad_dto, offer_type, object_type)
        self._store_raw_payload(session, ad_dto)
        self._record_price(session, saved_ad, previous)

    def _outdate(self, session, saved_ad: Ad):
        previous = price_state_of(saved_ad)
        saved_ad.outdate()
        self._record_price(session, saved_ad, previous)

    @staticmethod
    def _ensure_entity(session, cache: set, entity_id, factory):
        if entity_id is None:
            return
        if entity_id not in cache:
            session.merge(factory())
            session.flush()
            cache.add(entity_id)

    def scrape_search(self, url: str) -> Optional[SearchResultDto]:
        try:
            return self.with_retry(self.__scraper.scrape_search, url)
        except Exception as e:
            logger.error(f"Giving up on search page {url} - {e}")
            return None

    def scrape_ad(self, url: str, offer_type: OfferType, object_type: ObjectType):
        try:
            self.with_retry(self.__scrape_ad, url, offer_type.name, object_type.name)
        except Exception as e:
            logger.error(f"Giving up on ad {url} - {e}")

    def __scrape_ad(self, url: str, offer_type: str, object_type: str):
        is_update_enabled: bool = self.__update_if_older_than_days is not None

        if url is None or url == "":
            return

        if url in self.existing_ad_urls:
            if is_update_enabled:
                if self.__update_if_older_than_days is None:
                    raise Exception("Some shit to make IDE happy")
                with self.__database_manager.get_session() as session:
                    saved_ad: Ad | None = session.query(Ad).filter(Ad.url == url).first()
                    if saved_ad is None:
                        logger.warning(f"URL {url} found in cache but not in DB")
                        return
                    if saved_ad.should_update(self.__update_if_older_than_days):
                        logger.info(f"Updating ad with url: {url} - last update was at - {saved_ad.modified_at}")
                        ad_dto: AdDto | None = self._fetch_ad(url)
                        if ad_dto:
                            self._refresh(session, saved_ad, ad_dto, offer_type, object_type)
                        else:
                            self._outdate(session, saved_ad)
                            logger.warning(f"Marking as outdated - {saved_ad.id} - {url}")
                    else:
                        logger.info(f"Skipping update of url: {url} - last update was at - {saved_ad.modified_at}")
            else:
                logger.info(f"URL {url} already exists, skipping...")
            return

        ad_dto: AdDto | None= self._fetch_ad(url)
        if ad_dto:
            if ad_dto.id in self.existing_ad_ids:
                with self.__database_manager.get_session() as session:
                    saved_ad = session.query(Ad).filter(Ad.id == ad_dto.id).first()

                    if saved_ad is not None:
                        self._refresh(session, saved_ad, ad_dto, offer_type, object_type)
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
                self._store_dimensions(session, ad)
                saved_ad = session.merge(Ad.from_dataclass(ad, offer_type, object_type))
                session.flush()
                self._store_raw_payload(session, ad)
                self._record_price(session, saved_ad, None)
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
            only_missing_locations: bool = False,
            shard: Optional[tuple[int, int]] = None,
    ):
        """Re-scrape ads already stored in the DB and refresh them (status, price, ...).

        Used to detect listings that are no longer active - the scraper still returns
        the ad's status, so Ad.update() picks up the change.
        """
        with self.__database_manager.get_session() as session:
            query = session.query(Ad.id).filter(Ad.status == AdStatus.ACTIVE)
            if shard:
                index, count = shard
                query = query.filter(Ad.id.op('%')(count) == index - 1)
            if only_missing_locations:
                query = query.filter(Ad.city_id.is_(None))
            elif city:
                query = query.outerjoin(Ad.city).filter(or_(City.name.ilike(city), Ad.city_id.is_(None)))
            if min_price is not None:
                query = query.filter(Ad.price_value >= min_price)
            if max_price is not None:
                query = query.filter(Ad.price_value <= max_price)
            # TODO: enable once offer_type/object_type are populated in the DB
            # if object_types:
            #     query = query.filter(Ad.object_type.in_(object_types))
            # if offer_types:
            #     query = query.filter(Ad.offer_type.in_(offer_types))
            if self.__update_if_older_than_days and not only_missing_locations:
                threshold = datetime.now() - timedelta(days=self.__update_if_older_than_days)
                query = query.filter(or_(Ad.scraped_at.is_(None), Ad.scraped_at < threshold))
            if only_missing_locations:
                query = query.order_by(Ad.scraped_at.desc().nulls_last())
            else:
                query = query.order_by(Ad.scraped_at.asc())
            ad_ids = [row.id for row in query.all()]

        logger.info(f"Found {len(ad_ids)} ads in DB to verify")
        for ad_id in ad_ids:
            self.update_existing_ad(ad_id)

    def update_existing_ad(self, ad_id: int):
        try:
            self.with_retry(self.__update_existing_ad, ad_id)
        except Exception as e:
            logger.error(f"Giving up on updating ad {ad_id} - {e}")

    def __update_existing_ad(self, ad_id: int):
        with self.__database_manager.get_session() as session:
            saved_ad: Ad | None = session.query(Ad).filter(Ad.id == ad_id).first()
            if saved_ad is None:
                return

            url = saved_ad.url
            ad_dto: AdDto | None = self._fetch_ad(url)
            if ad_dto is None:
                self._outdate(session, saved_ad)
                logger.warning(f"Marking as outdated - {ad_id} - {url}")
                return

            # Preserve offer_type/object_type - they are not part of the scraped JSON
            self._refresh(session, saved_ad, ad_dto, saved_ad.offer_type, saved_ad.object_type)
            logger.info(f"Updated ad {ad_id} - status: {ad_dto.status} - url: {url}")


def scrape(
        urls: list[SearchUrl],
        max_age_days: int = 30,
        request_delay_seconds: float = 0.0,
        store_raw_payloads: bool = True,
):
    scraper = OtodomScraper(request_delay_seconds)
    db_manager = DatabaseManager()
    db_manager.create_all_tables()
    scraping_context = ScrapingContext(db_manager, scraper, max_age_days, store_raw_payloads)

    for url in urls:
        page_number = 1
        total_pages = 1
        while page_number <= total_pages:
            url.page_number = page_number
            search_result = scraping_context.scrape_search(url.build())
            if search_result is not None:
                total_pages = search_result.total_pages
                for ad_item in search_result.items:
                    scraping_context.scrape_ad(ad_item.url, url.offer_type, url.object_type)
            page_number += 1


def update_ads(
        city: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        object_types: Optional[list[ObjectType]] = None,
        offer_types: Optional[list[OfferType]] = None,
        max_age_days: int = 30,
        request_delay_seconds: float = 0.0,
        store_raw_payloads: bool = True,
        only_missing_locations: bool = False,
        shard: Optional[tuple[int, int]] = None,
):
    scraper = OtodomScraper(request_delay_seconds)
    db_manager = DatabaseManager()
    db_manager.create_all_tables()
    scraping_context = ScrapingContext(db_manager, scraper, max_age_days, store_raw_payloads)

    scraping_context.update_existing_ads(
        city=city,
        min_price=min_price,
        max_price=max_price,
        object_types=[o.name for o in object_types] if object_types else None,
        offer_types=[o.name for o in offer_types] if offer_types else None,
        only_missing_locations=only_missing_locations,
        shard=shard,
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


def parse_shard(value: Optional[str]) -> Optional[tuple[int, int]]:
    if value is None:
        return None
    index, separator, count = value.partition("/")
    if not separator or not index.isdigit() or not count.isdigit():
        raise typer.BadParameter(f"--shard must look like 1/2, got {value}")
    index, count = int(index), int(count)
    if count < 1 or not 1 <= index <= count:
        raise typer.BadParameter(f"--shard {value}: the first number must be between 1 and {count}")
    return index, count


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
        max_age_days: int = typer.Option(
            30, '--max-age-days', min=0,
            help="Re-scrape a stored ad once its last check is older than this many days (0 = always)."
        ),
        request_delay_seconds: float = typer.Option(
            2.0, '--request-delay', min=0,
            help="Minimum pause between requests to otodom, in seconds; each pause adds up to 50% random jitter."
        ),
        store_raw_payloads: bool = typer.Option(
            True, '--store-raw/--no-store-raw',
            help="Keep the latest compressed page JSON of every scraped ad in ad_raw_payloads, for re-parsing later."
        ),
        only_missing_locations: bool = typer.Option(
            False, '--only-missing-locations',
            help="Temporary: the update pass re-scrapes only active ads with no city, regardless of --max-age-days "
                 "and --city. Repairs ads stored without a location before the reverse geocoding fix.",
        ),
        shard: Optional[str] = typer.Option(
            None, '--shard',
            help="Split the update pass between processes: 1/2 takes ads with id % 2 == 0, 2/2 the rest. "
                 "Give every process the same total.",
        ),
):
    if district and not city:
        raise typer.BadParameter("--district requires --city")
    if city and not voivodeship:
        raise typer.BadParameter("--city requires --voivodeship")
    if not scrape_enabled and not update_enabled:
        raise typer.BadParameter("At least one of --scrape / --update must be enabled")
    if only_missing_locations and not update_enabled:
        raise typer.BadParameter("--only-missing-locations requires --update")
    parsed_shard = parse_shard(shard)
    if parsed_shard and not update_enabled:
        raise typer.BadParameter("--shard requires --update")

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

    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    heartbeat = ServiceHeartbeatWriter(database_manager, SCRAPER_SERVICE, " ".join(sys.argv)).start()
    attach_database_logging(database_manager, SCRAPER_SERVICE)

    while True:
        if scrape_enabled:
            heartbeat.report(ServiceStatus.RUNNING, phase="zbieranie nowych ogłoszeń",
                             detail={"adresy_wyszukiwania": len(urls)})
            scrape(urls, max_age_days, request_delay_seconds, store_raw_payloads)
            logger.info("All listings have been scraped.")

        if update_enabled:
            heartbeat.report(ServiceStatus.RUNNING, phase="odświeżanie zapisanych ogłoszeń")
            update_ads(
                city=city,
                min_price=min_price if min_price else None,
                max_price=max_price if max_price else None,
                object_types=build_object_types(houses, apartments),
                offer_types=build_offer_types(sale, rent),
                max_age_days=max_age_days,
                request_delay_seconds=request_delay_seconds,
                store_raw_payloads=store_raw_payloads,
                only_missing_locations=only_missing_locations,
                shard=parsed_shard,
            )
            logger.info("All existing ads have been verified.")

        logger.info("Cycle complete. Restarting in 60 seconds...")
        heartbeat.report(ServiceStatus.IDLE, phase="przerwa między cyklami")
        sleep(60)


if __name__ == '__main__':
    typer.run(main)
