import logging
import sys
from typing import Optional

import typer
from sqlalchemy import select

from data.ad_dto import AdDto
from data.location_resolver import complete_location
from data.models import Ad, AdRawPayload
from data.raw_payload import as_page_json, decompress_payload
from database import DatabaseManager
from main import ScrapingContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def main(
        apply: bool = typer.Option(False, '--apply', help="Write the re-parsed values. Without it only counts changes."),
        limit: Optional[int] = typer.Option(None, '--limit', min=1, help="Re-parse at most this many stored payloads."),
        only_missing_location: bool = typer.Option(
            True, '--only-missing-location/--all', help="Only ads that have no city yet."
        ),
):
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    context = ScrapingContext(database_manager, scraper=None, store_raw_payloads=False)

    with database_manager.get_session() as session:
        statement = select(AdRawPayload.ad_id).join(Ad, Ad.id == AdRawPayload.ad_id).order_by(AdRawPayload.ad_id)
        if only_missing_location:
            statement = statement.where(Ad.city_id.is_(None))
        if limit:
            statement = statement.limit(limit)
        ad_ids = list(session.execute(statement).scalars())

    logger.info("Re-parsing %d stored payloads (%s)", len(ad_ids), "apply" if apply else "dry run")
    changed = 0
    for start in range(0, len(ad_ids), BATCH_SIZE):
        with database_manager.get_session() as session:
            for ad_id in ad_ids[start:start + BATCH_SIZE]:
                changed += _reparse(session, context, ad_id)
            if not apply:
                session.rollback()
        logger.info("Processed %d of %d, %d with a changed location", min(start + BATCH_SIZE, len(ad_ids)), len(ad_ids), changed)


def _reparse(session, context: ScrapingContext, ad_id: int) -> int:
    ad = session.get(Ad, ad_id)
    raw = session.get(AdRawPayload, ad_id)
    dto = AdDto.from_json(as_page_json(decompress_payload(raw.payload)))
    if ad is None or dto is None:
        return 0

    complete_location(dto, context.location_index)
    before = (ad.province_id, ad.county_id, ad.city_id, ad.district_id)
    scraped_at = ad.scraped_at

    context._store_dimensions(session, dto)
    ad.update(dto, ad.offer_type, ad.object_type)
    ad.scraped_at = scraped_at

    return int(before != (ad.province_id, ad.county_id, ad.city_id, ad.district_id))


if __name__ == "__main__":
    typer.run(main)
