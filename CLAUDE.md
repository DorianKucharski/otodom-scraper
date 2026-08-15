# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Three independent applications over one PostgreSQL database (PostGIS + pg_trgm):

1. **Scraper** (`main.py`) - walks otodom.pl search results, scrapes each listing, persists normalized data.
2. **Enricher** (`enrich.py`) - scores stored ads with an LLM (photos + description) into its own tables. Never touched by the scraper.
3. **API + web UI** (`api/`, `web/`) - FastAPI search over scraper data *and* AI scores, plus a React frontend.

Tests live in `tests/` (unittest, mirrors the source tree). There is no linter. `README.md` covers running the stack on Docker and narrowing the scrape/enrich scope.

## Commands

Dependencies are managed with **uv** (`pyproject.toml` + `uv.lock`; there is no `requirements.txt`).

```bash
# Create/sync the local venv from the lockfile
uv sync

# Run the scraper (requires DATABASE_URL in .env). Defaults scrape ALL of Poland,
# houses+apartments, sale+rent, in an infinite loop.
uv run python main.py

# Scope a run with CLI flags (typer). Examples:
uv run python main.py --no-rent --apartments --no-houses --voivodeship mazowieckie --city warszawa --max-price 800000
uv run python main.py --voivodeship malopolska --city krakow --district stare-miasto

# Run only one of the two passes
uv run python main.py --scrape --no-update    # discover new ads only
uv run python main.py --no-scrape --update    # refresh ads already in the DB only

# Smoke-test the scraper/parser against a single live ad URL (no DB needed):
uv run python otodom_scraper.py

# Add / remove a dependency (updates pyproject.toml + uv.lock)
uv add <package>
uv remove <package>

# Tests (unittest, no DB or API key needed)
uv run python -m unittest discover -s tests -t .
```

### Enricher

```bash
# Both stages in a forever loop (needs DATABASE_URL + ANTHROPIC_API_KEY)
uv run python enrich.py

# Iterate on prompts against one live ad, printing JSON, writing nothing
uv run python enrich.py --ad-url "https://www.otodom.pl/pl/oferta/..." --dry-run

# Scope a run, once, bounded
uv run python enrich.py --voivodeship lubelskie --city lublin --limit 20 --once

# Only one stage
uv run python enrich.py --screen --no-evaluate
uv run python enrich.py --no-screen --evaluate

# Re-run ads whose stored result is still current
uv run python enrich.py --force --limit 5
```

### API and frontend

```bash
uv run uvicorn api.main:app --reload      # http://localhost:8000/docs
cd web && npm install && npm run dev      # http://localhost:5173, proxies /api to :8000
cd web && npm run build                   # writes web/dist, which the API serves at /
```

Flag rules enforced in `main()`: `--district` requires `--city`; `--city` requires `--voivodeship`; at least one of `--scrape` / `--update` must stay enabled.

### Docker
```bash
docker compose up -d --build   # uses .env; restarts on failure
```
Three services: `otodom-scrapper`, `otodom-enricher` (same image, different `command`) and `otodom-api` (own `Dockerfile.api`, multi-stage: Node builds `web/`, Python serves it). Pushing to `main` builds + signs both images to GHCR (matrix over `Dockerfile` and `Dockerfile.api`) and SSH-deploys.

## Required environment

`.env` must define `DATABASE_URL`, e.g. `postgresql://user:pass@localhost:5432/otodom_db` (see `.env.example`). `DatabaseManager` raises on startup if it is missing.

The enricher additionally needs `LLM_PROVIDER` (`anthropic` default, or `openai`) and the matching key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). `EnricherConfig.from_env()` raises on startup naming the missing variable. Everything else has a default - see `.env.example`.

## Architecture

Data flows: **HTTP fetch → DTO parse → ORM model → DB upsert**, orchestrated by `main.py`.

`main()` runs two independent passes inside one forever-loop, both enabled by default:
1. **scrape pass** (`scrape()`) — walks search-result pages to discover and insert new ads.
2. **update pass** (`update_ads()` → `ScrapingContext.update_existing_ads`) — re-scrapes ads already stored in the DB, stalest first (`ORDER BY Ad.modified_at ASC`), to refresh price/status. Only `AdStatus.ACTIVE` rows are considered; filtering by `object_type`/`offer_type` is commented out because those columns are not backfilled yet.

- **`otodom_scraper.py` (`OtodomScraper`)** — the only network layer. Uses `cloudscraper` to bypass Cloudflare, then extracts the page's embedded Next.js JSON from `<script type="application/json">` and hands it to the DTOs. otodom is a Next.js app: there is **no HTML scraping of fields** — everything comes from that JSON blob. Status `410` (gone) is treated as a valid response, not an error.

- **DTOs (`data/`)** — plain dataclasses with `from_json` classmethods that defensively read the scraped JSON.
  - `data/ad_dto.py` — the listing detail (`AdDto`) plus nested property/location/owner/image/characteristic DTOs. **`CharacteristicKey`** is an important enum: otodom returns a generic `characteristics` list (keyed strings like `build_year`, `m`, `rent`, `floor_no`), and `AdDto.get_characteristic()` looks these up. See "Characteristics fallback" below.
  - `data/search_dto.py` — search-results page (`SearchResultDto` + `SearchAdDto`), including pagination (`total_pages` drives the page loop). Maps otodom enum strings (e.g. rooms `"THREE"`→3, floor `"GROUND"`→0) to ints.
  - `data/search_url.py` — builds otodom search URLs from `OfferType`/`ObjectType`/`Location`/price filters. `Location` normalizes Polish characters (ą→a etc.) for URL slugs. Note the city path is intentionally tripled (`/{city}/{city}/{city}`) — that's otodom's URL shape. `ObjectType` covers nine categories, but the CLI only exposes `HOUSE` and `APARTMENT`; `build_urls()` also skips the impossible `INVESTMENT`+`RENT` and `ROOM`+`SALE` combinations.

- **`data/models.py`** — SQLAlchemy 2.0 ORM (`DeclarativeBase`). `Ad` is the central table with one-to-many detail tables (`AdImage`, `AdFeature`, `AdCharacteristic`, `AdFlatEquipment`, etc.) and FKs to dimension tables (`Province`/`County`/`City`/`District`/`Owner`). Each model has a `from_dataclass()` that converts the matching DTO. Geospatial: `latitude`/`longitude` plus a PostGIS `location_point` (`POINT`, SRID 4326). Heavy use of GIN trigram indexes on text columns for search.

- **`database.py` (`DatabaseManager`)** — engine/session factory. `create_all_tables()` first creates the `postgis` and `pg_trgm` extensions, then `Base.metadata.create_all`, then the raw-SQL read models (`ad_all_features` view, `district_price_stats` materialized view + index). `refresh_district_price_stats()` is called by the enricher at the start of every cycle. `get_session()` is a context manager that commits on success / rolls back on exception. There are **no migrations** — schema is created directly from the models, so a model change generally needs a manual schema drop/recreate (`drop_tables()` in `main.py`). New tables added later are created on the next start without touching existing ones.

- **`main.py` (`ScrapingContext` + `scrape`)** — the orchestrator and the trickiest part:
  - On init it loads **in-memory sets of all existing IDs/URLs** (ads, owners, provinces, …) to avoid per-item DB lookups during a run.
  - `scrape_ad(url)` decides skip vs. insert vs. update: known URL + stale (`Ad.should_update`, default 30 days) → re-scrape and update; new URL whose ad ID already exists → update; otherwise insert. `_ensure_entity` upserts dimension rows (owner/city/…) via `session.merge` before inserting the ad.
  - A scrape that yields no `AdDto` (removed listing, redirect) is not an error: the row is marked `AdStatus.OUTDATED` via `Ad.outdate()` instead of being deleted. `AdStatus` also carries the upstream values `REMOVED`, `REMOVED_BY_USER`, `REMOVED_BY_PARENT_AD`, which come from the scraped JSON through `Ad.update()`.
  - `offer_type`/`object_type` are **not** part of the scraped JSON — they are threaded in from the search URL that found the ad, and the update pass re-passes the values already on the row so they are not wiped.
  - `with_retry` wraps each ad scrape (3 tries, 10s sleep).
  - `scrape()` loops every search URL across all pages; `main()` wraps both passes in a `while True` with a 60s pause — **the process is designed to run forever**.

## The AI enrichment layer (`enricher/`, `enrich.py`)

Two stages, both writing one row per ad into tables the scraper never touches (`Ad` has **no** relationship to them on purpose - a relationship would let `session.merge(ad)` in the scraper cascade into and wipe them):

1. **Screening** (`ad_screenings`, default `claude-haiku-4-5`, text only) - drops ads that are not a real single flat to live in (whole investments, shares, bailiff auctions, commercial units) and pulls facts out of the free-text description that the portal's own feature list omits.
2. **Evaluation** (`ad_evaluations`, default `claude-sonnet-5`, up to 8 photos) - ten 1-10 scores, `renovation_needed`, `style_tag`, a Polish summary, strengths, concerns, and a free-form `attributes` JSONB bag.

- **Prompts live in `enricher/prompts/*.md` and `*.jinja2`, never in Python.** `prompt_version` is a hash of the template pair, so editing a prompt automatically invalidates every stored result - there is no version constant to bump.
- **Re-runs are gated by `content_fingerprint`** (title, description, feature lists, image URLs, area, rooms, floor, condition). A scraper update pass that only bumps `modified_at` costs zero tokens. Evaluation additionally re-runs when the price drifts more than `EVALUATION_PRICE_DRIFT_THRESHOLD` from `price_at_evaluation`, because the model scores `value_for_money_score`.
- **Failed rows carry `attempts`** and stop being retried after `selector.MAX_ATTEMPTS`.
- **Structured output** uses one JSON Schema per stage (`enricher/schema.py`) fed to Anthropic via `output_config.format` and to OpenAI via `response_format`. Structured outputs forbid free-form objects, so key/value bags travel as arrays of `{key, value}` and collapse into dicts in `enricher/results.py`.
- **Adding a score** means: `SCORE_DEFINITIONS` in `enricher/schema.py`, a column + index on `AdEvaluation`, a `min_<name>` field on `AdSearchQuery`, and a label in `web/src/api/types.ts`. `SCORE_FIELD_NAMES` drives the runner, the API filter loop and the sort enum, so those need no edit.
- `district_price_stats` (materialized view, refreshed by the enricher each cycle) feeds the district median into the evaluation prompt. Without it "opłacalność" would be guesswork.

## The search API (`api/`)

- `api/query.py` is the only place that turns filters into SQL; `api/schemas.py` is the HTTP contract (pydantic lives at the boundary only, dataclasses everywhere else).
- Feature filters run against the `ad_all_features` view (UNION ALL over the seven detail tables), which also backs `features_count`.
- `Ad.flat_floor` is a string like `FLOOR_3`, so numeric floor filters go through the `FLOOR_NUMBER` CASE expression in `api/query.py`.

### Characteristics fallback (important when touching `Ad._set_properties`)
A listing's structured fields (area, rent, floor, rooms, build year, building type/material/heating) are populated from `ad_data.property` when present. When `property` is absent, the code falls back to reading the generic `characteristics` list via `CharacteristicKey`. If you add a new derived field, wire up **both** paths.

## Conventions

- DTO `from_json` methods must stay null-safe (return `None`/defaults on missing keys) — the upstream JSON is inconsistent across listing types (apartment/house/investment/room).
- New scraped fields flow through all four layers: DTO → `from_json` → ORM column + `from_dataclass`/`update` → (if derivable) `CharacteristicKey` fallback.
- `schemas/` holds JSON-schema references for the upstream payloads (`ad_schema_apartment_sale.json`, `ad_schema_house_sale.json`, `search_apartment_rent_schema.json`) — read them before adding a field. `examples/example_queries.sql` holds sample SQL against the resulting schema.
- Knowledge shared by more than one application lives in `data/` (`feature_groups.py`, `description.py`, `read_models.py`). The enricher and the API must not import from each other; `api/` importing `enricher/schema.py` for `SCORE_FIELD_NAMES` is the one deliberate exception, because that tuple is the contract between the two.
- No comments in source. Explanations belong here, in the commit message or in the MR description.
