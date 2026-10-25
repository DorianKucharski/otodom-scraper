# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Three independent applications over one PostgreSQL database (PostGIS + pg_trgm):

1. **Scraper** (`main.py`) - walks otodom.pl search results, scrapes each listing, persists normalized data.
2. **Enricher** (`enrich.py`) - scores stored ads with an LLM (photos + description) into its own tables. Never touched by the scraper.
3. **API + web UI** (`api/`, `web/`) - FastAPI search over scraper data *and* AI scores, plus a React frontend and an LLM search assistant.

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

Flag rules enforced in `main()`: `--district` requires `--city`; `--city` requires `--voivodeship`; `--radius-km` requires `--city` and must be one of otodom's radii (`data/area_scope.py`); at least one of `--scrape` / `--update` must stay enabled. With `--radius-km` the update pass and the enricher also take stored ads within that distance of the city's PRG boundary.

### Docker
```bash
docker compose up -d --build   # uses .env; restarts on failure
```
Three services: `otodom-scrapper`, `otodom-enricher` (same image, different `command`) and `otodom-api` (own `Dockerfile.api`, multi-stage: Node builds `web/`, Python serves it). Pushing to `main` runs the unit tests and the web build, then SSH-deploys: the server fast-forwards its checkout in `/opt/github/otodom-scraper` and runs `docker compose up -d --build`. The images are built on the server because compose uses local `build:` tags; publishing them to a registry would need `image:` pointing there.

## Required environment

`.env` must define `DATABASE_URL`, e.g. `postgresql://user:pass@localhost:5432/otodom_db` (see `.env.example`). `DatabaseManager` raises on startup if it is missing.

The enricher additionally needs `LLM_PROVIDER` (`anthropic` default, or `openai`) and the matching key (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). `EnricherConfig.from_env()` raises on startup naming the missing variable. Everything else has a default - see `.env.example`.

## Architecture

Data flows: **HTTP fetch → DTO parse → ORM model → DB upsert**, orchestrated by `main.py`.

`main()` runs two independent passes inside one forever-loop, both enabled by default:
1. **scrape pass** (`scrape()`) — walks search-result pages to discover and insert new ads.
2. **update pass** (`update_ads()` → `ScrapingContext.update_existing_ads`) — re-scrapes ads already stored in the DB, stalest first (`ORDER BY Ad.modified_at ASC`), to refresh price/status. Only `AdStatus.ACTIVE` rows are considered; filtering by `object_type`/`offer_type` is commented out because those columns are not backfilled yet.

- **`otodom_scraper.py` (`OtodomScraper`)** — the only network layer. Uses `cloudscraper` to bypass Cloudflare, then extracts the page's embedded Next.js JSON from `<script type="application/json">` and hands it to the DTOs. otodom is a Next.js app: there is **no HTML scraping of fields** — everything comes from that JSON blob. Statuses `410` (gone) and `404` (a removed listing now answers with otodom's 404 page) are valid responses, not errors: they parse to no `AdDto`, so the ad is marked outdated instead of being retried three times. Error messages leave out the response body, which is a whole HTML page.

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
  - `ScrapeRetry` (`ScrapingContext.with_retry`) wraps every search page and ad scrape: 3 tries with a 10s pause for ordinary errors. A 403/429 from otodom's CloudFront is an IP-wide block, so `OtodomScraper` raises `OtodomBlockedError` instead; that pauses 1 min doubling to 30 min (the backoff carries across items until a request succeeds), opens a fresh cloudscraper session, and does not use up the ordinary tries. An item that still fails is logged and skipped, never raised - a crash restarts the container, which walks the search pages from page 1 again and never reaches the update pass. `--request-delay` (default 2 s, plus up to 50% jitter) spaces out every request so blocks are rarer in the first place.
  - `scrape()` loops every search URL across all pages; `main()` wraps both passes in a `while True` with a 60s pause — **the process is designed to run forever**.

## Location (`data/location_resolver.py`)

Since June 2026 otodom sends `ad.location.address` with `province`/`county`/`city`/`district` all null (only the street sometimes survives). Every ad inserted after that had no location: 30k active ads by October, and city-scoped runs could not see them. The update pass joined on `City`, and so did the enricher, so those ads were never refreshed or scored.

- The location now comes from two other places in the page JSON, parsed into `LocationHintsDto`: `ad.location.reverseGeocoding.locations` (levels `voivodeship`/`city_or_village`/`district`/`residential`, slug paths, no numeric ids) and `pageProps.adTrackingData` (`city_id` is otodom's numeric city id, the same one `cities` is keyed by; `region_id`/`subregion_id` are the province and county codes).
- `complete_location()` fills only what the old `address` format left empty. Province and county resolve by code, city by the tracking id. District resolves by `(city_id, code)` learned from existing ads, because district codes repeat across cities (`zwierzyniec`); failing that, a unique code that no other city uses. Anything unresolved gets a stable negative id from `synthetic_location_id(level, path)`, so it can never collide with otodom's own ids. `LocationIndex` is built once in `ScrapingContext` and grows as new rows are created.
- `Ad.update()` fills location fields only when the new value is present and never sets them back to NULL, so a re-scrape repairs an ad and a format change cannot wipe one. Every scrape path now calls `_store_dimensions` before `update()`.
- The city-filtered update pass also includes ads with `city_id IS NULL`, so broken rows inside a scoped deployment get re-scraped and repaired. `--only-missing-locations` (temporary, see README) restricts the update pass to active ads with no city, ignores the age threshold and walks them most-recently-seen first (the stalest ones are almost all removed listings, while recently seen ones are still on otodom), to burn through the backlog in a one-off container. `--shard i/n` splits any update pass by `id % n`. Without it, parallel processes load the same stalest-first list and mostly re-scrape the same ads, because `update_existing_ads` takes its id list once and never re-checks it.

### Raw payloads (`ad_raw_payloads`, `data/raw_payload.py`)

Every successful ad scrape keeps the latest zlib-compressed `{ad, adTrackingData, developmentData}` from the page (5-8 kB per ad; the full page is ~100-140 kB but mostly UI state). The rest of `pageProps` (current user, experiments, cookies) is deliberately not stored. `--no-store-raw` turns it off. When a parser bug or an upstream format change is found, `uv run python reparse.py` re-parses the stored payloads without touching otodom: a dry run by default, `--apply` to write, `--all` to go beyond ads with no city. `scraped_at` is kept, because nothing was actually re-checked.

## The AI enrichment layer (`enricher/`, `enrich.py`)

Two stages, both writing one row per ad into tables the scraper never touches (`Ad` has **no** relationship to them on purpose - a relationship would let `session.merge(ad)` in the scraper cascade into and wipe them):

1. **Screening** (`ad_screenings`, default `claude-haiku-4-5`, text only) - drops ads that are not one dwelling (whole investments with no single unit's price and area, several units sold together, shares, bailiff auctions, commercial units) and pulls facts out of the free-text description that the portal's own feature list omits. Houses, flats under construction and developer cessions pass on purpose: until October 2026 the prompt rejected them, which hid ~6000 active offers, nearly all of Kraków's primary market and its detached houses. The evaluation stage handles renders through `photo_trust_score`.
2. **Evaluation** (`ad_evaluations`, default `claude-sonnet-5`, up to 8 photos) - ten 1-10 scores, `renovation_needed`, `style_tag`, a Polish summary, strengths, concerns, and a free-form `attributes` JSONB bag.

- **Prompts live in `enricher/prompts/*.md` and `*.jinja2`, never in Python.** `prompt_version` is a hash of the template pair, so editing a prompt automatically invalidates every stored result - there is no version constant to bump.
- **Re-runs are gated by `content_fingerprint`** (title, description, feature lists, image URLs, area, rooms, floor, condition). A scraper update pass that only bumps `modified_at` costs zero tokens. Evaluation additionally re-runs when the price drifts more than `EVALUATION_PRICE_DRIFT_THRESHOLD` from `price_at_evaluation`, because the model scores `value_for_money_score`.
- **Failed rows carry `attempts`** and stop being retried after `selector.MAX_ATTEMPTS`.
- **Structured output** uses one JSON Schema per stage (`enricher/schema.py`) fed to Anthropic via `output_config.format` and to OpenAI via `response_format`. Structured outputs forbid free-form objects, so key/value bags travel as arrays of `{key, value}` and collapse into dicts in `enricher/results.py`.
- **Photos travel as URLs by default.** If the provider cannot fetch them (otodom's CDN does reject it), `enricher/image_fallback.py` retries the ad once with `cloudscraper`-downloaded base64 images and remembers that for the rest of the process. `LLM_DOWNLOAD_IMAGES=true` skips the failing first attempt.
- **`Ad.update()` must not invent a change.** `modified_at` carries otodom's own timestamp and `scraped_at` records when we last checked; `should_update()` reads `scraped_at`. Stamping `modified_at` with `datetime.now()` on every refresh made every stored ad look modified, which woke the enricher's SQL pre-filter for the whole table each cycle and, with `--limit`, pinned it to the newest ads forever.
- **Candidate order puts never-processed ads first** (`_ids_of` in `enricher/selector.py`). Without that, a bounded run keeps re-examining ads that already have a current verdict and never reaches the backlog.
- **The LLM layer is shared** (`llm/`: clients, `LlmSettings`, pricing, retry, prompt loading), because the API's assistant calls the same models and must not import from `enricher/`. `cost_usd_for` strips a dated snapshot suffix: Anthropic answers `claude-haiku-4-5` requests as `claude-haiku-4-5-20251001`, and before that every screening row had a NULL cost that the daily budget silently skipped.
- **Evaluation requests** (`ad_evaluation_requests`, `enricher/requests.py`): the API only queues ad ids, and `EvaluationRequestWorker` in the looping enricher polls every 10 s on its own thread, screening and evaluating them with `AdFilter(ad_ids=...)`, which bypasses the location and price scope. It has its own `ENRICHER_REQUEST_DAILY_BUDGET_USD`, counted over the requested ads only, so a background cycle that has burnt the main budget does not block what a user explicitly asked for, and the other way round. `request_outcome` turns the stored rows into done/rejected/failed.
- **Cost controls:** `ENRICHER_DAILY_BUDGET_USD` (10 USD when unset) stops the loop for the rest of the 24h window (`enricher/budget.py`). It is checked before every ad through `RunGuard`, not only before a cycle: one cycle takes the whole backlog, and after the location repair a single cycle evaluated ~3000 ads (~100 USD) past a 5 USD limit. An `LlmAccountError` (no credits, rejected key, OpenAI `insufficient_quota`) halts the rest of the run the same way and is not recorded as the ad's failure; before that, every remaining ad burnt its `attempts` on the account error and was never retried after the top-up. Halted requested evaluations stay pending. The budget sums cost by `screened_at`/`evaluated_at`, so both carry `onupdate`: `session.merge` rewrites an existing row, and with only a server default a re-run kept the first run's timestamp and its cost never counted. `LLM_MAX_DESCRIPTION_CHARACTERS` caps the free text in both prompts, and `--dry-run` without `--ad-url` or `--limit` caps itself at `DRY_RUN_LIMIT`. Images dominate the evaluation prompt: `medium` is 655x491 (~429 tokens each), `small` is 314x236 (~99). See README for the measured per-stage cost.
- **Adding a score** means: `SCORE_DEFINITIONS` in `enricher/schema.py`, a column + index on `AdEvaluation`, a `min_<name>` field on `AdSearchQuery`, and a label in `web/src/api/types.ts`. `SCORE_FIELD_NAMES` drives the runner, the API filter loop and the sort enum, so those need no edit.
- `district_price_stats` (materialized view, refreshed by the enricher each cycle) feeds the district median into the evaluation prompt. Without it "opłacalność" would be guesswork.

## Service monitoring (`monitoring/`)

Both long-running processes report into the database so the UI can show status and logs without a Docker socket (the API container is exposed on a port with no authentication; mounting the socket there would be root on the host).

- `ServiceHeartbeatWriter.start()` spawns a daemon thread that rewrites the last reported state every 30 s, so a multi-hour scrape does not look like a hang. `report()` changes the state and writes immediately. `STALE_AFTER_SECONDS` in `monitoring/services.py` decides when the API calls a service stale.
- `DatabaseLogHandler` is attached to the root logger and buffers records, flushing on size or age. `service_logs` is a ring buffer trimmed to the newest 2000 rows per service. A database failure prints to stderr and pauses writing for a minute rather than raising inside logging.
- Adding a service means a constant in `monitoring/services.py`, plus `start()` and `attach_database_logging()` in its entrypoint. `/api/services` picks it up from `_KNOWN_SERVICES`.

## Market signals (`data/market_signals.py`, table `ad_market_signals`)

A derived table, recomputed in full by `refresh_market_signals` (enricher, every `MARKET_SIGNALS_INTERVAL_HOURS`, or `uv run python signals.py`). It is the answer to two expensive mistakes made while house-hunting: an offer that looked 39% below the district median was a 120 m² flat (which skews price per metre) pinned to the last Kraków street before the border while it actually stood in Modlnica, and it had been relisted every month for half a year after its owners had asked 70k less themselves. When judging any offer, read these signals before the AI scores.

- **Lineage** (`data/listing_lineage.py`): the same dwelling across relistings and advertisers. Candidates share a rounded area within 0.5%, rooms, floor and build year (when known) and lie within 3 km (agencies move pins). Two listings live at the same time are linked only as an exact duplicate (same owner, price and text), so identical units of one development stay apart; primary-market pairs need near-identical text. Each listing gets at most one predecessor and one successor, so groups are chains. `ended_at` is only trusted for `removed_by_user`/`removed_by_parent_ad` (otodom's `modifiedAt` is the removal time); `outdated` means a 404 with no data, so its end is unknown and never blocks a link. Text similarity is the max of title and description Jaccard, because removed ads have masked descriptions.
- **Price history**: `ad_price_observations` gets a row from `ScrapingContext._refresh/_outdate/__save_new_ad` whenever price, area or status changes. Rows older than this feature are a single backfilled observation, so `first_price` for old ads is the price we first saw, not the original one.
- **Comparables** (`data/comparables.py`): median price per m² of at least 10 other dwellings (one per lineage group) of the same offer/object type, area ±35%, active or seen in the last 180 days, within the smallest radius of 750 m to 10 km that yields enough. Grid index plus bisect on area, pure Python (no numpy in the image), about a minute for the whole table.
- **Transactions** (`data/rcn.py`, `rcn_transactions`, `load_transactions.py`): RCN flat sales from GUGiK's open WFS (`ms:lokale`), loaded by 2 km bbox tiles around chosen cities (paging with a TERYT filter returns random empty pages). One RCN transaction can cover several lokale with only a total price, so a sale is used only when it has its own `LOK_CENA_BRUTTO` or is the only lokal in its transaction. Compared over the last 2 years for the secondary market and 1 year for the primary one, same market first: in Kraków secondary sales stayed at 14.5-15k zł/m2 from mid-2024 to mid-2026 while primary ones rose about 20%.
- **Street transactions** (`data/street_sales.py`): RCN sales whose `UL:` address has the same `street_key` as the listing's street, within 1.5 km (long streets), area ±35%, at least 3, same market first. A radius mixes submarkets: Dożynkowa's 1.5 km median was 14.3k zł/m² because of Nowa Górka next door, while its own sale was 10.6k.
- **Previous sale** (`data/previous_sales.py`): an RCN flat sale within 150 m of the pin, same area within 1% (round areas like 50 m2 identify nothing and are skipped), same rooms, price between 0.35 and 2 times the asking price, sold before the listing appeared. More than two such sales means a block of identical flats, so nothing is reported.
- **Area flags** (`data/area_checks.py`): a usable area in the description smaller than the listed one (ignoring the area of one level, an attic or a garage mentioned just before it), slopes or floor area, and storage counted into the total. Only descriptions matching `AREA_TEXT_PATTERN` are loaded.
- **Location flags** (`data/location_checks.py`): `admin_areas` holds PRG city and gmina polygons (`load_boundaries.py`; Kraków, Warszawa and Łódź are merged from their delegatury/dzielnice by the 4-digit TERYT prefix; A03 gmina codes have no underscore). Flags: `pin_outside_city`, `near_city_border` (< 1 km), `other_place_in_text` (a locality name stem within 6 km of the pin, only checked within 2.5 km of a border), `border_in_text`, `lineage_city_mismatch`. Villages have no PRG polygon, so only towns are checked.
- **OSM context** (`load_osm.py`, `data/overpass.py`): one Overpass fetch per table over the bbox of the `RCN_CITIES` boundaries plus a margin, refreshed by the enricher every `RCN_REFRESH_DAYS` (`osm_due`).
- **Developer price lists** (`data/developer_prices.py` parses, `data/developer_price_lists.py` loads, `data/developer_matches.py` matches; tables `developer_price_lists`, `developer_units`, `developer_unit_prices`; `load_developer_prices.py`, run by the enricher every `DEVELOPER_PRICES_REFRESH_HOURS` with `RCN_CITIES`): since 11.09.2025 developers must publish a daily price list on dane.gov.pl in the ministry's template. The loader pages `/institutions` for `institution_type == developer` (the API ignores type filters), then each developer's `/institutions/{id}/datasets` (listing `/datasets` stops at 10 000 results of ~29 000), always with `sort=id`: without it the pages overlap and ~1150 of ~6900 developers were never seen, takes each dataset's newest resource (`sort=-data_date`), skips datasets with nothing newer than 45 days and parses xlsx/csv by header keywords, because wording and column order vary (the sales office's town must not be taken for the investment's: only `lokalizacji przedsięwzięcia/inwestycji/zadania` columns count). JSON and XML (`data/structured_price_lists.py`) have no common schema: they are flattened into one record per innermost object, inheriting the scalars of every enclosing object (investment city, building number), with keys turned into header text (`investments buildings properties price`), history lists skipped. Headers that do not fit the template go through a looser synonym set (`city`/`miasto`, `unit no`/`nr lokalu`, `price brutto`/`cena aktualna`) matched on the last words of the key, so `developer phone number` is never a unit and `sales office city` never the town. An XML holding no units but `resource/url` + `dataDate` entries is a harvester feed: the loader follows the link for that day. The `prices` JSON (`productName`, `gross`, `investmentName`) has no town at all and stays unplaced. Lists rejected only for a format that is now parsed are re-probed on the next run. Units are kept when their town or gmina is a PRG name around `RCN_CITIES` and keyed by institution plus town/street/number/unit, because some developers open a new dataset every day. History comes from roughly monthly files on the first load and from newer files after that (weekly after a gap, so daily runs take each new file); a price change adds a `developer_unit_prices` row. A unit number that comes back with an area more than 2% off is another flat (Orion's unit 5 was 51.7 m² in January and 29.8 m² in July), so its history restarts. A unit missing from its developer's newest file in that town is gone (sold or reserved). Matching needs the same town and area within 0.05 m², plus the street key or a price within 1% of any price the unit had, and never more than 15% off (Skanska's Awangarda on Mogilska matched NOHO's units on the same street by area alone); a different room count rules a candidate out; equally good candidates from different developers or prices are ambiguous and skipped.
- **Street check** (`data/street_checks.py`, `osm_streets`): every named OSM highway way with a `key`, the last word of its ascii-folded name ("Wincentego Bogdanowskiego" → `bogdanowskiego`), so first names, ranks and house numbers in the listing's street do not matter. Same-key ways anywhere in the bbox count, which can only shorten the distance. Only pins inside a PRG town polygon with some OSM street within ~300 m are checked (coverage), and only 1-15 km counts: beyond that it is a namesake in another town, and pins 20 km off are `pin_outside_city` anyway. `pin_far_from_street`, and then nuisance flags are skipped because they would be measured from a wrong pin. `os.`/`osiedle`/`Rynek` are skipped: Kraków's osiedla are areas, and "os. Strusia" matched a Strusia street 28 km away.
- **Nuisances** (`data/nuisances.py`, `nuisance_features`): OSM motorway/trunk ways (with links), main/branch railways and paved runways of at least 1800 m (Balice; the grass strips and the disused Czyżyny runway are skipped) around `RCN_CITIES`, refreshed every `RCN_REFRESH_DAYS`, tunnels skipped. Nearest road and railway come from a geometry KNN (top 3, then the exact geography distance); the approach corridor (8 km past each runway end, 400 m half-width widening 5%) is computed in Python. Flags `near_expressway` (300 m), `near_railway` (150 m), `under_approach`. Pins are often a few hundred metres off, so these are prompts to check, not facts.
- The enricher runs `signals.py` as a subprocess so the ~1 GB peak (274k ads, texts as 32-hash bottom-k sketches, descriptions streamed, rows inserted in chunks) is returned to the OS and a failure keeps the previous signals. Keep new per-ad data out of memory-wide dicts; stream or keep only flagged results.
- The enricher passes signals into the evaluation prompt through existing template fields (`address` with location warnings and nearby nuisances, `created_at_label`, `market_stats.position_label`). Editing the template would change `prompt_version` and re-evaluate every stored ad at real cost; filling existing fields does not. Phrases live in `data/signal_phrases.py`, shared with the assistant's rank cards.
- Removed ads come back from otodom with `description`, `street` and owner name replaced by `***`. `Ad.update()` keeps the stored values (`is_masked`), and `_store_raw_payload` does not overwrite a stored payload with a masked one. About 21k ads had already lost their description before this.

## The search API (`api/`)

- `/api/facets` is served from `facets_cache` (`api/cache.py`): computed once at startup in a background thread, then served stale and refreshed in the background after 10 minutes. Computing it takes ~5 s on the full table, so no request should wait for it. Cities alone are ~10k values; `MultiSelect` in the UI renders at most 100 unselected options and relies on its search box for the rest.
- `api/query.py` is the only place that turns filters into SQL; `api/schemas.py` is the HTTP contract (pydantic lives at the boundary only, dataclasses everywhere else).
- Feature filters run against the `ad_all_features` view (UNION ALL over the seven detail tables), which also backs `features_count`.
- **Auth** (`api/auth.py`): one shared `APP_PASSWORD`, plus a free-text name typed at login. Both go into an HMAC-signed, one-year, HttpOnly cookie whose key is derived from the password, so changing it signs everyone out. The middleware guards `/api/*`, `/docs` and `/openapi.json` except `/api/health` and `/api/auth/*`. Without `APP_PASSWORD` everything is open, but the UI still asks for a name so history has an author. Routers read the name through `get_user_name`. HTTPS comes from Mikrus' wykr.es domain (Cloudflare in front of the bare port), so `api/https.py` decides "was this HTTPS" from `X-Forwarded-Proto`. That drives the cookie's `Secure` flag and, when `APP_PUBLIC_URL` is set, a 308 redirect for everything else that arrived over plain HTTP (the bare port included), except `/api/health`.
- **Tracking** (`ad_tracking` + `ad_tracking_events`, router `api/routers/tracking.py`, rules in `api/tracking.py`): one current row per ad plus an append-only history, where each status change or note is one event with a comment and an author. Like the enrichment tables, `Ad` has no relationship to them. `viewing_at` is naive wall-clock time as typed in the browser, while `created_at`/`updated_at` are timezone-aware. Search hides `DISMISSED_TRACKING_STATUSES` unless `hide_dismissed=false`. These hold user data that cannot be re-scraped, so think twice before `drop_tables()`.
- **Offer and object type are inferred for old rows** (`data/inferred_types.py`). `Ad.offer_type`/`object_type` are NULL for most ads scraped before those columns existed, and the update pass re-passes the NULL. Sale vs rent falls back to `market` (PRIMARY/SECONDARY means sale, rent ads carry ALL or an empty string) and then to price below `RENT_PRICE_CEILING`; it agrees with known rows 99.5% of the time. Flat vs house falls back to floor, building type, `property_type`, and finally title keywords (`HOUSE_TITLE_PATTERN` before `FLAT_TITLE_PATTERN`; one pattern string serves Postgres `~*` and Python `re`), agreeing 98.6% of the time with about 1% left unknown. Roughly 64k ads were parsed with no floor, area or building type, so the title is their only signal. A `/inwestycja/` URL wins over everything as `INVESTMENT`: a developer project with renders, price 0, no area and no city (the parser does not read that page format). Because there is no city, the city-scoped enricher never sees them, and that is fine, since AI scores on renders would be meaningless.
- The SQL rules are compiled into the `ad_inferred_types` materialized view (created in `create_all_tables`, refreshed `CONCURRENTLY` by the enricher every cycle, ~3 s). The title regex costs ~1.4 s per query when evaluated live. `api/query.py` filters on `coalesce(view, column)`, so ads inserted since the last refresh fall back to the scraper's own value. `offer_type_of`/`object_type_of` are the Python twins used by the mappers; keep both in sync.
- Search runs in two steps: `SearchStatements.page` selects only the ids of one page, and `rows_for(ids)` loads full rows for those ids. Sorting the full joined rows (description, evaluation and so on, ~2.8 kB each) before `LIMIT` was the main cost of a filtered search.
- **Labels live in `api/labels.py`**: Polish label plus an optional explanation per upstream code, served as `label`/`description` on facets and applied by the mappers to display-only fields. Filters still take the raw codes. Features arrive from otodom in Polish *and* as English codes (`balkon`/`balcony`, `winda`/`LIFT`), and `_FEATURE_SYNONYMS` groups them under one label. In the current data every ad with an English code also carries the Polish spelling, so the facet takes the larger of the per-spelling counts (`merge_feature_counts`) instead of an exact `count(DISTINCT ad_id)`, which took 8 s over the 2.7M-row view. The facet value is that label, and `feature_values_for` expands a selected label or raw value back into every raw spelling. Ambiguous Polish words get a prefix (`drewniane` is a fence, `WOODEN` a window).
- `Ad.flat_floor` is a string like `FLOOR_3`, so numeric floor filters go through the `FLOOR_NUMBER` CASE expression in `api/query.py`. It must only cast codes matching `^FLOOR_[0-9]+$`: `FLOOR_HIGHER_10` (11 there), `CELLAR` (-1) and `GARRET` (no number, excluded by `exclude_top_floor`) also occur, and a blind cast failed every floor-filtered query.

### The assistant (`api/assistant/`, router `api/routers/assistant.py`)

Natural-language search in two LLM calls, both recorded with their cost in `assistant_calls` and capped by `ASSISTANT_DAILY_BUDGET_USD`:

1. `interpret` turns the message (plus earlier messages and the previous plan, so a follow-up is a correction) into a `SearchPlan`: an ordinary `AdSearchQuery` the UI loads into the filter panel, keywords, soft criteria (`must`/`nice`) and a sort. Anthropic structured outputs allow at most 24 optional and 16 union-typed parameters, so the schema has no nullable field: numeric bounds travel as a list of `{field, value}` pairs and everything else is a possibly empty array. Place names are matched against the facet values (accent- and case-insensitive) and dropped with a warning when unknown, because a misspelt city would otherwise silently search all of Poland. A place that is not an otodom district becomes `near` (lat/lng/radius) on the existing radius filter. A radius above 10 km means the surroundings ("pod Warszawą"), so `plan_from_payload` drops the city and district filters the model tends to add alongside it. The prompt tells the model to filter only on hard conditions, since most ads do not tick the features a filter would require.
2. `rank` loads `ASSISTANT_CANDIDATES` ids with the plan's filters, ordered by `keyword_relevance` (a sum of ILIKE hits over title and description, ~1.4 s even country-wide) and then the AI overall score, builds a compact text card per ad (facts, features, screening facts, evaluation, description head) and asks for at most ten `{ad_id, fit_score, headline, matches, gaps}`. `ad_id` is an integer enum of the candidate ids, so the model cannot invent one. Polish runs at ~1.6 characters per token: 40 evaluated Kraków candidates with 1200 description characters were 75k tokens, 0.29 USD and 41 s, which is why the defaults are 30 and 800 (30 unevaluated houses: 22k tokens, 0.11 USD, 31 s). Cloudflare cuts a request at 100 s, so keep `ASSISTANT_RANK_EFFORT` low.

The candidate pool is filters plus keywords, not embeddings. pgvector is not installed on the database host yet; it would add recall for soft wishes phrased differently from the description, and would plug in as a second source of candidate ids in `load_candidates`.

### Characteristics fallback (important when touching `Ad._set_properties`)
A listing's structured fields (area, rent, floor, rooms, build year, building type/material/heating) are populated from `ad_data.property` when present. When `property` is absent, the code falls back to reading the generic `characteristics` list via `CharacteristicKey`. If you add a new derived field, wire up **both** paths.

## Conventions

- DTO `from_json` methods must stay null-safe (return `None`/defaults on missing keys) — the upstream JSON is inconsistent across listing types (apartment/house/investment/room).
- New scraped fields flow through all four layers: DTO → `from_json` → ORM column + `from_dataclass`/`update` → (if derivable) `CharacteristicKey` fallback.
- `schemas/` holds JSON-schema references for the upstream payloads (`ad_schema_apartment_sale.json`, `ad_schema_house_sale.json`, `search_apartment_rent_schema.json`) — read them before adding a field. `examples/example_queries.sql` holds sample SQL against the resulting schema.
- Knowledge shared by more than one application lives in `data/` (`feature_groups.py`, `description.py`, `read_models.py`). The enricher and the API must not import from each other; `api/` importing `enricher/schema.py` for `SCORE_FIELD_NAMES` is the one deliberate exception, because that tuple is the contract between the two.
- No comments in source. Explanations belong here, in the commit message or in the MR description.
