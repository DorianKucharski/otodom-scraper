from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Iterator, Optional

import requests
from psycopg2.extras import Json, execute_values
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .derived_tables import ensure_table
from .developer_prices import PARSED_FORMATS, PriceListUnit, parse_price_list, place_name
from .structured_price_lists import harvester_link
from .models import DeveloperPriceList, DeveloperUnit, DeveloperUnitPrice

logger = logging.getLogger(__name__)

DANE_GOV_API = "https://api.dane.gov.pl/1.4"
DATASET_URL = "https://dane.gov.pl/pl/dataset/{dataset_id}"
DEVELOPER_INSTITUTION = "developer"
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 120
MAX_FILE_BYTES = 30 * 1024 * 1024
TRIES = 3
WORKERS = 6
STALE_AFTER_DAYS = 45
RECHECK_IRRELEVANT_DAYS = 30
HISTORY_STEP_DAYS = 30
UPDATE_STEP_DAYS = 7
PROGRESS_EVERY = 1000
SAME_AREA_RATIO = 0.02

_TARGET_PLACES = text("""
WITH target AS (
    SELECT ST_Union(ST_Buffer(geom::geography, :margin)::geometry) AS geom
    FROM admin_areas
    WHERE level = 'city' AND city_name = ANY(:cities)
)
SELECT DISTINCT a.name, a.city_name
FROM admin_areas a, target
WHERE a.geom && target.geom AND ST_Intersects(a.geom, target.geom)
""")

_UNIT_COLUMNS = (
    "institution_id", "dataset_id", "unit_key", "developer", "investment", "voivodeship", "gmina", "town", "street", "building_number",
    "unit", "kind", "area", "rooms", "floor", "price", "price_per_m2", "price_since", "price_with_extras", "extras",
    "extras_value", "prospectus_url", "first_seen", "last_seen", "first_price", "lowest_price", "highest_price",
)

_INSERT_UNITS = f"INSERT INTO developer_units ({', '.join(_UNIT_COLUMNS)}) VALUES %s RETURNING id, unit_key"

_UPDATE_UNITS = """
UPDATE developer_units u SET
    dataset_id = v.dataset_id::bigint, developer = v.developer, investment = v.investment, street = v.street, kind = v.kind, area = v.area::numeric,
    rooms = v.rooms::smallint, floor = v.floor, price = v.price::int, price_per_m2 = v.price_per_m2::int,
    price_since = v.price_since::timestamp, price_with_extras = v.price_with_extras::int, extras = v.extras::jsonb,
    extras_value = v.extras_value::int, prospectus_url = v.prospectus_url, last_seen = v.last_seen::timestamp,
    lowest_price = v.lowest_price::int, highest_price = v.highest_price::int
FROM (VALUES %s) AS v(
    id, dataset_id, developer, investment, street, kind, area, rooms, floor, price, price_per_m2, price_since, price_with_extras,
    extras, extras_value, prospectus_url, last_seen, lowest_price, highest_price
)
WHERE u.id = v.id
"""

_BACKDATE_UNITS = """
UPDATE developer_units u SET
    first_seen = v.observed_at::timestamp,
    first_price = v.price::int,
    lowest_price = least(u.lowest_price, v.price::int),
    highest_price = greatest(u.highest_price, v.price::int)
FROM (VALUES %s) AS v(id, observed_at, price)
WHERE u.id = v.id AND v.observed_at::timestamp < u.first_seen
"""

_RESET_UNITS = """
WITH reset AS (
    UPDATE developer_units u SET first_seen = v.observed_at::timestamp, first_price = v.price::int
    FROM (VALUES %s) AS v(id, observed_at, price)
    WHERE u.id = v.id
    RETURNING u.id
)
DELETE FROM developer_unit_prices p USING reset WHERE p.unit_id = reset.id
"""

_INSERT_PRICES = "INSERT INTO developer_unit_prices (unit_id, observed_on, price, price_per_m2) VALUES %s"

_UPSERT_LIST = text("""
INSERT INTO developer_price_lists (
    dataset_id, institution_id, title, relevant, latest_data_date, processed_data_date, history_from, units_count,
    error, checked_at
) VALUES (
    :dataset_id, :institution_id, :title, :relevant, :latest_data_date, :processed_data_date, :history_from,
    :units_count, :error, :checked_at
)
ON CONFLICT (dataset_id) DO UPDATE SET
    institution_id = EXCLUDED.institution_id,
    title = EXCLUDED.title,
    relevant = EXCLUDED.relevant,
    latest_data_date = coalesce(EXCLUDED.latest_data_date, developer_price_lists.latest_data_date),
    processed_data_date = coalesce(EXCLUDED.processed_data_date, developer_price_lists.processed_data_date),
    history_from = coalesce(developer_price_lists.history_from, EXCLUDED.history_from),
    units_count = CASE WHEN EXCLUDED.processed_data_date IS NULL THEN developer_price_lists.units_count
                       ELSE EXCLUDED.units_count END,
    error = EXCLUDED.error,
    checked_at = EXCLUDED.checked_at
""")


@dataclass(frozen=True)
class Dataset:
    dataset_id: int
    institution_id: int
    title: str


@dataclass(frozen=True)
class Resource:
    resource_id: int
    data_date: date
    file_format: str
    url: Optional[str]


@dataclass(frozen=True)
class KnownList:
    relevant: Optional[bool]
    processed_data_date: Optional[date]
    checked_at: datetime
    error: Optional[str] = None

    def due(self, recheck_before: datetime) -> bool:
        if self.relevant is not False or self.checked_at < recheck_before:
            return True
        return (self.error or "").removeprefix("format ") in PARSED_FORMATS


@dataclass
class DatasetResult:
    dataset: Dataset
    relevant: Optional[bool] = None
    latest_data_date: Optional[date] = None
    snapshots: list[tuple[date, list[PriceListUnit]]] = field(default_factory=list)
    error: Optional[str] = None


class DaneGovClient:
    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", "otodom-scraper")

    def get_json(self, path_or_url: str, params: Optional[dict] = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{DANE_GOV_API}{path_or_url}"
        for attempt in range(1, TRIES + 1):
            try:
                response = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError):
                if attempt == TRIES:
                    raise
                time.sleep(5 * attempt)
        raise AssertionError("unreachable")

    def pages(self, path: str, params: Optional[dict] = None) -> Iterator[dict]:
        url, query = path, {"per_page": PAGE_SIZE, "page": 1, **(params or {})}
        while url:
            payload = self.get_json(url, query)
            yield from payload.get("data") or []
            url, query = (payload.get("links") or {}).get("next"), None

    def developer_institution_ids(self) -> set[int]:
        return {
            int(item["id"]) for item in self.pages("/institutions", {"sort": "id"})
            if (item.get("attributes") or {}).get("institution_type") == DEVELOPER_INSTITUTION
        }

    def developer_datasets(self, developers: set[int]) -> list[Dataset]:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            lists = pool.map(self.institution_datasets, sorted(developers))
            return [dataset for datasets in lists for dataset in datasets]

    def institution_datasets(self, institution_id: int) -> list[Dataset]:
        try:
            return [
                Dataset(int(item["id"]), institution_id, (item.get("attributes") or {}).get("title") or "")
                for item in self.pages(f"/institutions/{institution_id}/datasets", {"sort": "id"})
            ]
        except requests.RequestException as error:
            logger.info("Skipping datasets of institution %s: %s", institution_id, error)
            return []

    def latest_resource(self, dataset_id: int) -> Optional[Resource]:
        payload = self.get_json(f"/datasets/{dataset_id}/resources", {"per_page": 1, "sort": "-data_date"})
        resources = [resource_of(item) for item in payload.get("data") or []]
        return next((resource for resource in resources if resource is not None), None)

    def resources(self, dataset_id: int) -> list[Resource]:
        resources = (resource_of(item) for item in self.pages(f"/datasets/{dataset_id}/resources", {"sort": "data_date"}))
        return sorted((resource for resource in resources if resource is not None), key=lambda resource: resource.data_date)

    def download(self, resource: Resource) -> bytes:
        response = self._session.get(resource.url, timeout=DOWNLOAD_TIMEOUT_SECONDS, stream=True)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise ValueError(f"{resource.url} is larger than {MAX_FILE_BYTES} bytes")
            chunks.append(chunk)
        return b"".join(chunks)


def resource_of(item: dict) -> Optional[Resource]:
    attributes = item.get("attributes") or {}
    day = (attributes.get("data_date") or attributes.get("created") or "")[:10]
    try:
        data_date = date.fromisoformat(day)
    except ValueError:
        return None
    return Resource(
        resource_id=int(item["id"]),
        data_date=data_date,
        file_format=(attributes.get("format") or "").lower(),
        url=attributes.get("file_url") or attributes.get("link"),
    )


def sampled(resources: list[Resource], after: Optional[date], step_days: int) -> list[Resource]:
    candidates = [resource for resource in resources if after is None or resource.data_date > after]
    picked: list[Resource] = []
    for resource in candidates:
        if not picked or (resource.data_date - picked[-1].data_date).days >= step_days:
            picked.append(resource)
    if candidates and picked[-1] is not candidates[-1]:
        picked.append(candidates[-1])
    return picked


def in_places(unit: PriceListUnit, places: set[str]) -> bool:
    return place_name(unit.town) in places or place_name(unit.gmina) in places


def target_places(engine: Engine, cities: list[str], margin_m: int) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(_TARGET_PLACES, {"cities": cities, "margin": margin_m}).all()
    places = {place_name(name) for row in rows for name in row if name}
    places.discard(None)
    if not places:
        raise ValueError(f"No boundaries loaded for {cities}, run load_boundaries.py first")
    return places


def due(connection: Connection, refresh_hours: float, now: Optional[datetime] = None) -> bool:
    if refresh_hours <= 0:
        return False
    if not connection.dialect.has_table(connection, "developer_price_lists"):
        return True
    last = connection.execute(text("SELECT max(checked_at) FROM developer_price_lists")).scalar()
    return last is None or ((now or datetime.now()) - last).total_seconds() >= refresh_hours * 3600


def fetch_dataset(client: DaneGovClient, dataset: Dataset, known: Optional[KnownList], places: set[str],
                  today: date) -> DatasetResult:
    result = DatasetResult(dataset=dataset)
    try:
        latest = client.latest_resource(dataset.dataset_id)
        if latest is None:
            result.relevant = known.relevant if known else False
            return result
        result.latest_data_date = latest.data_date
        if known is not None and known.relevant:
            if known.processed_data_date is not None and latest.data_date <= known.processed_data_date:
                result.relevant = True
                return result
            result.relevant = True
            picked = sampled(client.resources(dataset.dataset_id), known.processed_data_date, UPDATE_STEP_DAYS)
            result.snapshots = list(_snapshots(client, picked, places))
            return result
        if (today - latest.data_date).days > STALE_AFTER_DAYS:
            result.relevant = False
            return result
        if latest.file_format not in PARSED_FORMATS:
            result.relevant = False
            result.error = f"format {latest.file_format or 'unknown'}"
            return result
        units = [unit for unit in units_of(client, latest) if in_places(unit, places)]
        result.relevant = bool(units)
        if units:
            history = [resource for resource in client.resources(dataset.dataset_id) if resource.data_date < latest.data_date]
            result.snapshots = list(_snapshots(client, sampled(history, None, HISTORY_STEP_DAYS), places))
            result.snapshots.append((latest.data_date, units))
    except Exception as error:
        result.error = f"{type(error).__name__}: {error}"[:500]
        if result.relevant is None and known is not None:
            result.relevant = known.relevant
    return result


def units_of(client: DaneGovClient, resource: Resource) -> list[PriceListUnit]:
    content = client.download(resource)
    units = parse_price_list(content, resource.file_format)
    if units or resource.file_format != "xml":
        return units
    link = harvester_link(content, resource.data_date)
    if link is None:
        return []
    url, file_format = link
    return parse_price_list(client.download(replace(resource, url=url, file_format=file_format)), file_format)


def _snapshots(client: DaneGovClient, resources: list[Resource], places: set[str]) -> Iterator[tuple[date, list]]:
    for resource in resources:
        if resource.file_format not in PARSED_FORMATS or not resource.url:
            continue
        try:
            units = [unit for unit in units_of(client, resource) if in_places(unit, places)]
        except Exception as error:
            logger.info("Skipping %s from %s: %s", resource.url, resource.data_date, error)
            continue
        if units:
            yield resource.data_date, units


def apply_snapshot(connection: Connection, institution_id: int, dataset_id: int, observed_on: date,
                   units: list[PriceListUnit]) -> int:
    observed_at = datetime.combine(observed_on, datetime.min.time())
    existing = {
        row.unit_key: row for row in connection.execute(text(
            "SELECT id, unit_key, area::float AS area, price, price_per_m2, lowest_price, highest_price, first_seen, "
            "last_seen "
            "FROM developer_units WHERE institution_id = :institution_id"
        ), {"institution_id": institution_id})
    }
    earlier, renumbered = [], []
    cursor = connection.connection.cursor()
    new_units, updates, prices = [], [], []
    for unit in units:
        row = existing.get(unit.key)
        if row is None:
            new_units.append(unit)
            continue
        if not same_area(row.area, unit.area):
            if observed_at > row.last_seen:
                renumbered.append((row.id, observed_at, unit.price))
                prices.append((row.id, observed_at, unit.price, unit.price_per_m2))
                updates.append(_update_row(row.id, dataset_id, unit, observed_at, unit.price, unit.price))
            continue
        if observed_at < row.first_seen:
            earlier.append((row.id, observed_at, unit.price))
            prices.append((row.id, observed_at, unit.price, unit.price_per_m2))
            continue
        if row.last_seen >= observed_at:
            continue
        lowest = min(filter(None, (row.lowest_price, unit.price)), default=None)
        highest = max(filter(None, (row.highest_price, unit.price)), default=None)
        updates.append(_update_row(row.id, dataset_id, unit, observed_at, lowest, highest))
        if (unit.price, unit.price_per_m2) != (row.price, row.price_per_m2):
            prices.append((row.id, observed_at, unit.price, unit.price_per_m2))
    if new_units:
        inserted = execute_values(
            cursor, _INSERT_UNITS, [_unit_row(institution_id, dataset_id, unit, observed_at) for unit in new_units],
            fetch=True,
        )
        prices.extend((unit_id, observed_at, unit.price, unit.price_per_m2)
                      for (unit_id, _), unit in zip(inserted, new_units))
    if renumbered:
        execute_values(cursor, _RESET_UNITS, renumbered)
    if updates:
        execute_values(cursor, _UPDATE_UNITS, updates)
    if earlier:
        execute_values(cursor, _BACKDATE_UNITS, earlier)
    if prices:
        execute_values(cursor, _INSERT_PRICES, prices)
    return len(new_units)


def same_area(known: Optional[float], seen: Optional[float]) -> bool:
    if not known or not seen:
        return True
    return abs(known - seen) <= max(known, seen) * SAME_AREA_RATIO


def _update_row(unit_id: int, dataset_id: int, unit: PriceListUnit, observed_at: datetime, lowest: Optional[int],
                highest: Optional[int]) -> tuple:
    return (
        unit_id, dataset_id, unit.developer, unit.investment, unit.street, unit.kind, unit.area, unit.rooms, unit.floor,
        unit.price, unit.price_per_m2, unit.price_since, unit.price_with_extras, Json(unit.extras), unit.extras_value,
        unit.prospectus_url, observed_at, lowest, highest,
    )


def _unit_row(institution_id: int, dataset_id: int, unit: PriceListUnit, observed_at: datetime) -> tuple:
    return (
        institution_id, dataset_id, unit.key, unit.developer, unit.investment, unit.voivodeship, unit.gmina, unit.town, unit.street,
        unit.building_number, unit.unit, unit.kind, unit.area, unit.rooms, unit.floor, unit.price, unit.price_per_m2,
        unit.price_since, unit.price_with_extras, Json(unit.extras), unit.extras_value, unit.prospectus_url,
        observed_at, observed_at, unit.price, unit.price, unit.price,
    )


def refresh_developer_prices(engine: Engine, cities: list[str], margin_m: int, now: Optional[datetime] = None,
                             client: Optional[DaneGovClient] = None) -> int:
    now = now or datetime.now()
    for table in (DeveloperPriceList.__table__, DeveloperUnit.__table__, DeveloperUnitPrice.__table__):
        ensure_table(engine, table)
    places = target_places(engine, cities, margin_m)
    client = client or DaneGovClient()
    developers = client.developer_institution_ids()
    datasets = client.developer_datasets(developers)
    logger.info("dane.gov.pl lists %d price-list datasets of %d developers", len(datasets), len(developers))
    with engine.connect() as connection:
        known = {
            row.dataset_id: KnownList(
                row.relevant, row.processed_data_date.date() if row.processed_data_date else None, row.checked_at,
                row.error,
            )
            for row in connection.execute(text(
                "SELECT dataset_id, relevant, processed_data_date, checked_at, error FROM developer_price_lists"
            ))
        }
    recheck_before = now - timedelta(days=RECHECK_IRRELEVANT_DAYS)
    todo = [
        dataset for dataset in datasets
        if dataset.dataset_id not in known or known[dataset.dataset_id].due(recheck_before)
    ]
    logger.info("Checking %d price lists (%d known, %d relevant)", len(todo), len(known),
                sum(1 for entry in known.values() if entry.relevant))
    today = now.date()
    stored_units = relevant = failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [
            pool.submit(fetch_dataset, client, dataset, known.get(dataset.dataset_id), places, today)
            for dataset in todo
        ]
        for number, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            stored_units += _store(engine, result, now)
            relevant += bool(result.relevant)
            failed += result.error is not None
            if number % PROGRESS_EVERY == 0:
                logger.info("Checked %d of %d price lists: %d relevant, %d failed, %d new units",
                            number, len(todo), relevant, failed, stored_units)
    logger.info("Price lists done: %d relevant, %d failed, %d new units", relevant, failed, stored_units)
    return stored_units


def _store(engine: Engine, result: DatasetResult, now: datetime) -> int:
    dataset = result.dataset
    new_units = 0
    with engine.begin() as connection:
        for observed_on, units in result.snapshots:
            new_units += apply_snapshot(connection, dataset.institution_id, dataset.dataset_id, observed_on, units)
        last = result.snapshots[-1] if result.snapshots else None
        connection.execute(_UPSERT_LIST, {
            "dataset_id": dataset.dataset_id,
            "institution_id": dataset.institution_id,
            "title": dataset.title,
            "relevant": result.relevant,
            "latest_data_date": result.latest_data_date,
            "processed_data_date": last[0] if last else None,
            "history_from": result.snapshots[0][0] if result.snapshots else None,
            "units_count": len(last[1]) if last else 0,
            "error": result.error,
            "checked_at": now,
        })
    return new_units
