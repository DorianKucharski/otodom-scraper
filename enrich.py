import json
import logging
import sys
from time import sleep
from typing import Optional

import typer

from data.models import ServiceStatus
from data.search_url import ObjectType, OfferType
from database import DatabaseManager
from enricher.config import EnricherConfig
from enricher.llm.factory import build_llm_client
from enricher.runner import EnrichmentRunner, RunSummary
from enricher.selector import AdFilter
from monitoring.heartbeat import ServiceHeartbeatWriter
from monitoring.log_handler import attach_database_logging
from monitoring.services import ENRICHER_SERVICE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_object_types(houses: bool, apartments: bool) -> tuple[str, ...]:
    object_types = []
    if houses:
        object_types.append(ObjectType.HOUSE.name)
    if apartments:
        object_types.append(ObjectType.APARTMENT.name)
    return tuple(object_types)


def build_offer_types(sale: bool, rent: bool) -> tuple[str, ...]:
    offer_types = []
    if sale:
        offer_types.append(OfferType.SALE.name)
    if rent:
        offer_types.append(OfferType.RENT.name)
    return tuple(offer_types)


def _summary_detail(summary: RunSummary) -> dict:
    return {
        "etap": summary.stage,
        "kandydaci": summary.candidates,
        "przetworzone": summary.processed,
        "pominięte": summary.skipped,
        "błędy": summary.failed,
        "koszt_usd": round(summary.cost_usd, 4),
    }


def print_dry_run(summary: RunSummary) -> None:
    for outcome in summary.outcomes:
        if outcome.result is None:
            continue
        payload = {"ad_id": outcome.ad_id, "stage": summary.stage, **outcome.result.as_dict()}
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def main(
        houses: bool = typer.Option(True, '--houses/--no-houses'),
        apartments: bool = typer.Option(True, '--apartments/--no-apartments'),
        sale: bool = typer.Option(True, '--sale/--no-sale'),
        rent: bool = typer.Option(True, '--rent/--no-rent'),
        voivodeship: Optional[str] = typer.Option(None, '--voivodeship'),
        city: Optional[str] = typer.Option(None, '--city'),
        district: Optional[str] = typer.Option(None, '--district'),
        min_price: Optional[int] = typer.Option(None, '--min-price'),
        max_price: Optional[int] = typer.Option(None, '--max-price'),
        ad_url: Optional[str] = typer.Option(None, '--ad-url', help="Enrich a single ad by its URL."),
        limit: Optional[int] = typer.Option(None, '--limit', help="Maximum number of ads per stage per cycle."),
        screen_enabled: bool = typer.Option(
            True, '--screen/--no-screen',
            help="Run the cheap text-only screening stage."
        ),
        evaluate_enabled: bool = typer.Option(
            True, '--evaluate/--no-evaluate',
            help="Run the full evaluation stage with images."
        ),
        force: bool = typer.Option(False, '--force', help="Re-run even when the stored result is up to date."),
        dry_run: bool = typer.Option(False, '--dry-run', help="Print results as JSON instead of writing them."),
        loop: bool = typer.Option(True, '--loop/--once'),
):
    if district and not city:
        raise typer.BadParameter("--district requires --city")
    if city and not voivodeship:
        raise typer.BadParameter("--city requires --voivodeship")
    if not screen_enabled and not evaluate_enabled:
        raise typer.BadParameter("At least one of --screen / --evaluate must be enabled")

    config = EnricherConfig.from_env()
    database_manager = DatabaseManager()
    database_manager.create_all_tables()
    runner = EnrichmentRunner(database_manager, build_llm_client(config), config)

    heartbeat = ServiceHeartbeatWriter(database_manager, ENRICHER_SERVICE, " ".join(sys.argv))
    if not dry_run:
        attach_database_logging(database_manager, ENRICHER_SERVICE)
        heartbeat.start()

    ad_filter = AdFilter(
        url=ad_url,
        voivodeship=voivodeship,
        city=city,
        district=district,
        min_price=min_price,
        max_price=max_price,
        object_types=build_object_types(houses, apartments),
        offer_types=build_offer_types(sale, rent),
        limit=limit,
    )

    logger.info(
        "Provider %s, screening model %s (prompt %s), evaluation model %s (prompt %s)",
        config.provider, config.screening_model, runner.screening_prompt_version,
        config.evaluation_model, runner.evaluation_prompt_version,
    )

    run_once = not loop or dry_run or ad_url is not None

    while True:
        heartbeat.report(ServiceStatus.RUNNING, phase="odświeżanie statystyk dzielnic")
        database_manager.refresh_district_price_stats()

        if screen_enabled:
            heartbeat.report(ServiceStatus.RUNNING, phase="przesiew opisów")
            summary = runner.screen(ad_filter, force=force, dry_run=dry_run)
            summary.log()
            heartbeat.report(ServiceStatus.RUNNING, phase="przesiew opisów", detail=_summary_detail(summary))
            if dry_run:
                print_dry_run(summary)

        if evaluate_enabled:
            heartbeat.report(ServiceStatus.RUNNING, phase="ocena ze zdjęciami")
            summary = runner.evaluate(ad_filter, force=force, dry_run=dry_run)
            summary.log()
            heartbeat.report(ServiceStatus.RUNNING, phase="ocena ze zdjęciami", detail=_summary_detail(summary))
            if dry_run:
                print_dry_run(summary)

        if run_once:
            heartbeat.report(ServiceStatus.STOPPED, phase="zakończono pojedynczy przebieg")
            return

        logger.info("Cycle complete. Restarting in %s seconds...", config.cycle_pause_seconds)
        heartbeat.report(ServiceStatus.IDLE, phase="przerwa między cyklami")
        sleep(config.cycle_pause_seconds)


if __name__ == '__main__':
    typer.run(main)
