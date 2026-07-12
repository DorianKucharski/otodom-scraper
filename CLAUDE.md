# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Scraper for **otodom.pl** (Polish real-estate portal). It walks paginated search results, scrapes each listing, and persists normalized data into **PostgreSQL** (with PostGIS + pg_trgm extensions). There is no test suite, linter, or README in this repo.

## Commands

Dependencies are managed with **uv** (`pyproject.toml` + `uv.lock`; there is no `requirements.txt`).

```powershell
# Create/sync the local venv from the lockfile
uv sync

# Run the scraper (requires DATABASE_URL in .env). Defaults scrape ALL of Poland,
# houses+apartments, sale+rent, in an infinite loop.
uv run python main.py

# Scope a run with CLI flags (typer). Examples:
uv run python main.py --no-rent --apartments --no-houses --voivodeship mazowieckie --city warszawa --max-price 800000
uv run python main.py --voivodeship malopolska --city krakow --district stare-miasto

# Smoke-test the scraper/parser against a single live ad URL (no DB needed):
uv run python otodom_scraper.py

# Add / remove a dependency (updates pyproject.toml + uv.lock)
uv add <package>
uv remove <package>
```

Flag rules enforced in `main()`: `--district` requires `--city`; `--city` requires `--voivodeship`.

### Docker
```powershell
docker compose up -d --build   # uses .env; restarts on failure
```
Pushing to `main` builds + signs a multi-arch image to GHCR and SSH-deploys to the server (`.github/workflows/docker-publish.yml`).

## Required environment

`.env` must define `DATABASE_URL`, e.g. `postgresql://user:pass@localhost:5432/otodom_db` (see `.env.example`). `DatabaseManager` raises on startup if it is missing.

## Architecture

Data flows: **HTTP fetch → DTO parse → ORM model → DB upsert**, orchestrated by `main.py`.

- **`otodom_scraper.py` (`OtodomScraper`)** — the only network layer. Uses `cloudscraper` to bypass Cloudflare, then extracts the page's embedded Next.js JSON from `<script type="application/json">` and hands it to the DTOs. otodom is a Next.js app: there is **no HTML scraping of fields** — everything comes from that JSON blob. Status `410` (gone) is treated as a valid response, not an error.

- **DTOs (`data/`)** — plain dataclasses with `from_json` classmethods that defensively read the scraped JSON.
  - `data/ad_dto.py` — the listing detail (`AdDto`) plus nested property/location/owner/image/characteristic DTOs. **`CharacteristicKey`** is an important enum: otodom returns a generic `characteristics` list (keyed strings like `build_year`, `m`, `rent`, `floor_no`), and `AdDto.get_characteristic()` looks these up. See "Characteristics fallback" below.
  - `data/search_dto.py` — search-results page (`SearchResultDto` + `SearchAdDto`), including pagination (`total_pages` drives the page loop). Maps otodom enum strings (e.g. rooms `"THREE"`→3, floor `"GROUND"`→0) to ints.
  - `data/search_url.py` — builds otodom search URLs from `OfferType`/`ObjectType`/`Location`/price filters. `Location` normalizes Polish characters (ą→a etc.) for URL slugs. Note the city path is intentionally tripled (`/{city}/{city}/{city}`) — that's otodom's URL shape.

- **`data/models.py`** — SQLAlchemy 2.0 ORM (`DeclarativeBase`). `Ad` is the central table with one-to-many detail tables (`AdImage`, `AdFeature`, `AdCharacteristic`, `AdFlatEquipment`, etc.) and FKs to dimension tables (`Province`/`County`/`City`/`District`/`Owner`). Each model has a `from_dataclass()` that converts the matching DTO. Geospatial: `latitude`/`longitude` plus a PostGIS `location_point` (`POINT`, SRID 4326). Heavy use of GIN trigram indexes on text columns for search.

- **`database.py` (`DatabaseManager`)** — engine/session factory. `create_all_tables()` first creates the `postgis` and `pg_trgm` extensions, then `Base.metadata.create_all`. `get_session()` is a context manager that commits on success / rolls back on exception. There are **no migrations** — schema is created directly from the models, so a model change generally needs a manual schema drop/recreate (`drop_tables()` in `main.py`).

- **`main.py` (`ScrapingContext` + `scrape`)** — the orchestrator and the trickiest part:
  - On init it loads **in-memory sets of all existing IDs/URLs** (ads, owners, provinces, …) to avoid per-item DB lookups during a run.
  - `scrape_ad(url)` decides skip vs. insert vs. update: known URL + stale (`Ad.should_update`, default 30 days) → re-scrape and update; new URL whose ad ID already exists → update; otherwise insert. `_ensure_entity` upserts dimension rows (owner/city/…) via `session.merge` before inserting the ad.
  - `with_retry` wraps each ad scrape (3 tries, 10s sleep).
  - `scrape()` loops every search URL across all pages; `main()` wraps the whole thing in a `while True` with a 60s pause — **the process is designed to run forever**.

### Characteristics fallback (important when touching `Ad._set_properties`)
A listing's structured fields (area, rent, floor, rooms, build year, building type/material/heating) are populated from `ad_data.property` when present. When `property` is absent, the code falls back to reading the generic `characteristics` list via `CharacteristicKey`. If you add a new derived field, wire up **both** paths.

## Conventions

- DTO `from_json` methods must stay null-safe (return `None`/defaults on missing keys) — the upstream JSON is inconsistent across listing types (apartment/house/investment/room).
- New scraped fields flow through all four layers: DTO → `from_json` → ORM column + `from_dataclass`/`update` → (if derivable) `CharacteristicKey` fallback.
- `examples/` and `schemas/` hold sample scraped JSON and JSON-schema references useful for understanding the upstream payload shape.
