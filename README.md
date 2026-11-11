# Otodom scraper + AI evaluation + search

Three independent processes on top of a single PostgreSQL database (PostGIS + pg_trgm):

| Service | What it does | Image |
| --- | --- | --- |
| `otodom-scrapper` | collects listings from otodom.pl into the database | `otodom-scraper:local` |
| `otodom-enricher` | evaluates the collected listings with an LLM (photos + description) | same image, different command |
| `otodom-api` | REST API + the built frontend on `:8000` | `otodom-api:local` |

The enricher writes only to `ad_screenings` and `ad_evaluations`. The scraper never touches them, so the next scraper run does not wipe the evaluations.

Tech stack: Python 3.12 (managed with `uv`), SQLAlchemy + GeoAlchemy2, FastAPI, Anthropic/OpenAI SDKs; frontend in `web/` (React + TypeScript, Vite); Docker Compose for deployment.

## Running from scratch

```bash
cp .env.example .env
# fill in DATABASE_URL and ANTHROPIC_API_KEY
docker compose up -d --build
```

The database and views are created automatically when the scraper and enricher start. The frontend is at `http://<host>:8000`, the API docs at `http://<host>:8000/docs`.

## Narrowing the scope

Parameters are set in `command:` in `docker-compose.yaml`, separately for the scraper and for the enricher.

```yaml
  otodom-scrapper:
    command: [ "python", "main.py",
               "--voivodeship=Małopolskie", "--city=Kraków",
               "--max-price=2000000", "--no-rent", "--no-houses" ]

  otodom-enricher:
    command: [ "python", "enrich.py",
               "--voivodeship=Małopolskie", "--city=Kraków",
               "--max-price=2000000", "--no-rent", "--no-houses" ]
```

**Keep both scopes in sync.** The enricher only evaluates what the scraper collected, so a wider enricher scope changes nothing, and a narrower one leaves some listings without evaluations.

Location names can be written with Polish diacritics and capitalised (`Kraków`, `Małopolskie`) or as an otodom slug (`krakow`, `malopolskie`) - both services accept either. `--district` requires `--city`, and `--city` requires `--voivodeship`.

### Shared scope flags

| Flag | Default | Note |
| --- | --- | --- |
| `--voivodeship=` | none (all of Poland) | |
| `--city=` | none | requires `--voivodeship` |
| `--district=` | none | requires `--city` |
| `--min-price=` / `--max-price=` | scraper `0` / `1000000`, enricher unlimited | |
| `--houses` / `--no-houses` | on | |
| `--apartments` / `--no-apartments` | on | |
| `--sale` / `--no-sale` | on | |
| `--rent` / `--no-rent` | on | |

### Scraper-only flags

| Flag | Purpose |
| --- | --- |
| `--scrape` / `--no-scrape` | collecting new listings |
| `--update` / `--no-update` | refreshing already stored listings (price, status) |
| `--max-age-days=` | how many days after the last check a listing gets refreshed (default `30`, `0` = always) |
| `--request-delay=` | minimum pause between requests to otodom in seconds, plus up to 50% random (default `2`) |

### Enricher-only flags

| Flag | Purpose |
| --- | --- |
| `--screen` / `--no-screen` | cheap text-only stage (Haiku) |
| `--evaluate` / `--no-evaluate` | full evaluation with photos (Sonnet) |
| `--limit=N` | at most N listings per stage in one cycle - **this is how you cap cost** |
| `--once` | a single pass instead of a loop |
| `--force` | re-evaluates even when the result is up to date |
| `--dry-run` | prints JSON, saves nothing |
| `--ad-url=` | one specific listing |

## Costs

Measured for the default models and eight photos in the `medium` variant (655x491, ~429 tokens each):

| Stage | Input | Output | Cost per listing |
| --- | --- | --- | --- |
| Screening (Haiku 4.5) | ~2,600 tok. | ~250 tok. | **~0.004 USD** |
| Evaluation (Sonnet 5) | ~6,500 tok. | ~600 tok. | **~0.029 USD** |

Of that, photos are 3,400 tokens, i.e. more than half of the evaluation input, and the model's response is about a third of the total cost and does not depend on the number of photos.

**Scale matters more than anything else.** Kraków up to 2 million PLN is close to 20k listings, i.e. about 80 USD for screening alone and about 500 USD for evaluations. Narrow the filters before you start turning the model knobs.

### What actually lowers the bill

| Change | Savings | Trade-off |
| --- | --- | --- |
| Narrower filters (district, tight price range, `--no-rent`) | proportional to the number of listings | none, it's usually what you're looking for anyway |
| `ENRICHER_DAILY_BUDGET_USD` (default 10) | hard daily ceiling, checked before every listing | evaluation is spread over several days |
| `LLM_MAX_IMAGES=5` | ~13% of evaluation cost | less material for `photo_trust_score` |
| `LLM_IMAGE_VARIANT=small` | ~30% of evaluation cost | 314x236 is not enough to judge finish quality |
| `LLM_MAX_DESCRIPTION_CHARACTERS=2000` | ~8% of evaluation cost, ~25% of screening | longer descriptions lose their ending |
| `EVALUATION_MODEL=claude-haiku-4-5` | ~65% of evaluation cost | noticeably weaker photo assessment, which is what this tool was built for |

### Is screening worth it

Screening costs 0.004 USD and saves 0.029 USD on every rejected listing, so it only pays off when it rejects more than 14 percent. Check your rate:

```sql
SELECT status, count(*), round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS procent
FROM ad_screenings GROUP BY status;
```

If fewer than 14 percent are rejected, screening adds to the bill instead of reducing it and it's better to turn it off with `--no-screen`. The only thing you lose then is the `extracted_attributes` extracted from the description.

Before running on a wide scope, set `--limit=20` and look at the results in the database.

## Everyday commands

```bash
# service status
docker compose ps

# live logs
docker compose logs -f otodom-enricher
docker compose logs -f otodom-scrapper
docker compose logs --tail=200 otodom-api

# restart one service without touching the rest
docker compose restart otodom-enricher

# stop one service
docker compose stop otodom-scrapper

# enricher only (the rest stopped)
docker compose stop otodom-scrapper otodom-api
docker compose up -d otodom-enricher

# everything back up
docker compose up -d
```

### After changing parameters in `command:`

No image rebuild needed, because `command` is not part of the image:

```bash
docker compose up -d otodom-enricher
```

Compose notices the configuration change and recreates just the container. `docker compose restart` is **not** enough - restart starts the old container with the old command.

### After changing `.env`

```bash
docker compose up -d
```

Same as above - environment variables are read when the container is created, not on restart.

### After changing code or prompts

```bash
docker compose up -d --build
```

Prompts (`enricher/prompts/`) are baked into the image, so changing them requires a rebuild. Note: `prompt_version` is a hash of the template, so **after a prompt change the enricher re-evaluates every listing in its scope**. With a wide scope this is a real cost - test the new prompt with `--dry-run` first, and only then deploy.

```bash
# rebuild just one image
docker compose build otodom-enricher && docker compose up -d otodom-enricher
```

## Iterating on prompts

The fastest loop needs neither Docker nor the database:

```bash
uv sync
uv run python enrich.py --ad-url "https://www.otodom.pl/pl/oferta/..." --dry-run
```

It prints the result of both stages as JSON and saves nothing. Prompts are edited in `enricher/prompts/`:

- `screening_system.md` - rejection criteria for stage 1
- `evaluation_system.md` - the 1-10 scoring rubric (this is where you calibrate what a 5 means and what an 8 means)
- `*_user.jinja2` - listing data inserted into the prompt

## When the enricher re-evaluates a listing

It does not repeat work on its own. A re-evaluation runs only when:

- the listing has not been evaluated yet,
- the content changed (title, description, features, photos, area, rooms, floor, condition),
- the prompt changed (`prompt_version`),
- the price drifted by more than `EVALUATION_PRICE_DRIFT_THRESHOLD` (default 5%) from the price at evaluation time,
- the previous attempt failed and has not yet used up three attempts.

A scraper `--update` run that only refreshes `modified_at` does not cost a single token.

## Model configuration (`.env`)

| Variable | Default | Note |
| --- | --- | --- |
| `LLM_PROVIDER` | `anthropic` | or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | - | missing = error at startup |
| `LLM_BASE_URL` | - | for OpenRouter, vLLM, Ollama |
| `SCREENING_MODEL` | `claude-haiku-4-5` | |
| `EVALUATION_MODEL` | `claude-sonnet-5` | |
| `LLM_MAX_IMAGES` | `8` | the main cost driver of stage 2 |
| `LLM_DOWNLOAD_IMAGES` | `false` | see below - set to `true` if otodom's CDN blocks the API |
| `LLM_EFFORT` | `medium` | skipped for models that don't accept it (Haiku) |
| `EVALUATION_PRICE_DRIFT_THRESHOLD` | `0.05` | |
| `ENRICHER_CONCURRENCY` | `4` | listings in parallel |
| `ENRICHER_CYCLE_PAUSE_SECONDS` | `300` | pause between cycles |

## Login

Set `APP_PASSWORD` in `.env` and restart `otodom-api`. Without this variable the API is open to anyone who reaches the port (a warning appears in the log).

- One password for everyone; at login you enter your name. It goes into the status history, so you can see who changed what.
- The cookie is valid for a year, so you log in once per device.
- Changing `APP_PASSWORD` logs out all devices, because the cookie is signed with it.
- All of `/api` (including service logs) and `/docs` are protected. The built frontend itself is public, but without a session it only shows the login screen.
- **HTTPS is provided by the domain from Mikrus** (the VPS provider; `https://steve138-30138.wykr.es`, via Cloudflare). The bare port `:30138` and `http://` on that domain still work unencrypted. That's why you should set `APP_PUBLIC_URL=https://steve138-30138.wykr.es`: every request that didn't arrive over HTTPS gets a 308 redirect to that address, so the login form is never shown over HTTP. `/api/health` is the exception.
- The API infers whether the connection was encrypted from the `X-Forwarded-Proto` header set by Cloudflare. Based on that the cookie also gets the `Secure` flag.

## My apartments

Any listing can be saved with a status from the details panel. Every status change and every note is a separate history entry with a comment, author and date (`ad_tracking_events`). The current state lives in `ad_tracking`.

| Status (UI label) | Meaning |
|---|---|
| Do sprawdzenia (to check) | caught my eye, needs a closer look |
| Do zadzwonienia (to call) | worth contacting |
| Po kontakcie (contacted) | waiting: they'll call back, send photos, didn't pick up |
| Umówione oglądanie (viewing scheduled) | requires a date and time |
| Obejrzane (viewed) | after the visit, optional 1-5 rating |
| Faworyt (favourite) | serious candidate after viewing |
| Negocjacje / oferta (negotiation / offer) | optional offer amount |
| Wybrane (chosen) | end of the search |
| Odrzucone (rejected) | giving up, reason in the comment |
| Niedostępne (unavailable) | sold, rented, withdrawn |

Any transition is allowed. Search hides rejected and unavailable listings by default; in the "Moje statusy" (my statuses) filter section you can turn that off or show only selected statuses. The **Moje mieszkania** (my apartments) tab groups saved listings by status and shows a list of scheduled viewings above them. Each saved listing shows the price change since it was saved.

The tables are created when the scraper or enricher starts, like all the others. `drop_tables()` in `main.py` drops them too.

## AI assistant

Above the results list in the **Wyszukiwarka** (search) tab there is an "Ask the assistant" field. You describe in plain language what you're looking for ("bright 3 rooms in Kraków up to 950k, close to greenery, not ground floor"), and the assistant works in two steps:

1. **Understanding** (`ASSISTANT_INTERPRET_MODEL`, Haiku by default, 0.005-0.01 USD, 5-7 s) turns the message into the regular filters on the left (city, district or the area around a point, price, area, rooms, floor), keywords for descriptions and a list of soft criteria ("must: bright interior", "nice to have: close to greenery"). You can see the filters and correct them. Soft criteria are deliberately not filters, because half of the listings don't mark them.
2. **Ranking** (`ASSISTANT_RANK_MODEL`, Sonnet 5 by default, measured 0.11 USD and 31 s for 30 listings without evaluations, up to about 0.20 USD when all of them have a photo evaluation) takes `ASSISTANT_CANDIDATES` (30) listings matching the filters, ordered by keyword hits and AI score. It reads their data, facts from screening, the photo evaluation and the start of the description, and then picks at most 10 with a match score, a justification and a list of unmet or uncertain points.

"Near Warsaw" or "around Kraków" means a 20-40 km radius from the centre, without a city filter, so it also catches listings that only have coordinates. A follow-up message in the same conversation ("cheaper", "what about Dębniki") adjusts the previous settings instead of starting from scratch. After manually changing filters, "Recalculate ranking" re-ranks with those filters.

**Evaluate from photos**: most listings outside the enricher's scope have no photo evaluation, so the ranking then relies on text only. This button adds them to the `ad_evaluation_requests` queue. The enricher checks it every 10 s in a separate thread, runs screening and full evaluation regardless of its `--city` and `--max-price` filters, and stores the result in the database like any other evaluation. When done, "Recalculate with new evaluations" appears. This only works when the enricher container is running in its loop.

| Variable | Default | Note |
| --- | --- | --- |
| `ASSISTANT_DAILY_BUDGET_USD` | `2` | total assistant cost over 24 h (`assistant_calls`); once exceeded the API returns 429 |
| `ENRICHER_REQUEST_DAILY_BUDGET_USD` | `3` | a separate limit for on-demand evaluations, independent of `ENRICHER_DAILY_BUDGET_USD` |
| `ASSISTANT_INTERPRET_MODEL` | `claude-haiku-4-5` | |
| `ASSISTANT_RANK_MODEL` | `claude-sonnet-5` | |
| `ASSISTANT_RANK_EFFORT` | `low` | higher makes the response longer, and Cloudflare drops the connection after 100 s |
| `ASSISTANT_CANDIDATES` | `30` | more candidates make ranking proportionally more expensive |
| `ASSISTANT_DESCRIPTION_CHARACTERS` | `800` | how much of each description goes into ranking |

The assistant uses the same key as the enricher (`ANTHROPIC_API_KEY`), so the `otodom-api` container must have it in `.env`. Without the key the panel shows that the assistant is disabled. Every call, with request, response and cost, is recorded in the `assistant_calls` table.

## Status and log view

The UI has three tabs: **Wyszukiwarka** (search), **Moje mieszkania** (my apartments) and **Status**. The Status tab shows:

- an indicator light and state for each service (Working / Waiting / No signal / Stopped), the current stage, time since the last heartbeat, uptime, statistics of the last cycle and the command the process was started with,
- logs of both services, switchable with tabs, with a level filter, text search and a choice of line count (200-2000).

This does not require access to the Docker socket. The scraper and enricher write a heartbeat to the `service_heartbeats` table and their logs to `service_logs`, from where the API reads them. Thanks to that the view also works when running outside containers.

- A background thread refreshes the heartbeat every 30 s, so a long scraping pass doesn't look like a hang. No heartbeat for more than 3 minutes means a stopped or hung process.
- `service_logs` is a ring buffer: the last 2000 lines per service are kept, older ones are deleted. The database doesn't grow forever.
- Writing logs must never crash the process: on a database error the handler dumps the message to stderr and pauses writes for a minute.
- `--dry-run` in the enricher writes neither logs nor heartbeats.

## Photos: URL vs. download

By default only the photo URLs are sent to the model, and the provider's API downloads them. Otodom's CDN may reject such a request:

```
Unable to download the file. Please verify the URL and try again.
```

The enricher handles this on its own: after the first such error it downloads photos through `cloudscraper` (just like the scraper) and sends them as base64, and subsequent listings in that process go this way straight away. In the log you'll see:

```
The API could not reach the image URLs of ad 68006816, downloading images from now on.
```

That one failed request repeats after every container restart. To avoid it, set in `.env`:

```
LLM_DOWNLOAD_IMAGES=true
```

The cost is downloading a few photos per listing on the enricher side, i.e. a bit of traffic and time, but zero extra tokens.

## Listing history, nearby prices and suspicious locations

Every listing gets a set of signals computed without an LLM in the `ad_market_signals` table. Search shows them as badges on the cards (hovering shows details), in the "Listing history and market" section of the details and in the "History and market" filters.

- **The same unit in successive listings.** Agencies take a listing down and re-post it every few weeks so it looks fresh. An owner first sells on their own, then hands the unit to an agency that raises the price. The scraper links such listings into a single "lineage" by area (to within 0.5%), rooms, floor, year of construction, distance (up to 3 km, because agencies move the pins) and similarity of title or description. Two listings live at the same time are linked only if it's the same advertiser, the same price and almost the same text, so identical units from one development stay separate. The lineage yields **time on market** counted from the first listing, the number of listings and advertisers, and the first, lowest and highest known price.
- **Price history.** From this version on the scraper records every change of price, area and status in `ad_price_observations`. Older listings have one observation from the last fetch, so the full price history builds up from now on.
- **Similar offers nearby.** Instead of the median of the whole district: the median price per square metre of at least 10 similar offers (same type, area ±35%, active or taken down within the last six months, each unit once) within a radius of 750 m to 10 km from the pin. The district median was misleading, because large units have a lower price per square metre, and the pin could point to a different district than the actual location.
- **Transaction prices from RCN.** `load_transactions.py` downloads apartment sales around the given cities from the Property Price Register (Rejestr Cen Nieruchomości, GUGiK's open WFS). The signals compare the price per square metre with the median of real transactions from the last 2 years (same market when there are enough of them, area ±35%, whole unit, open market). This is the only comparison that contains no asking prices.
- **Transactions on the same street.** A 1.5 km radius can mix an older estate at the city border with a luxury development next door. On Dożynkowa street the radius median was 14.3k PLN/m², while the only sale on that street was 10.6k. That's why a separate median of RCN sales on the same street is computed (address from RCN, up to 1.5 km from the pin, area ±35%, at least 3 transactions, same market first). In Kraków about 70% of secondary-market offers have one. In one case in three it differs from the radius median by more than 10%. Badge "±X% vs street". A street can mix things too: on Piltza (Ruczaj) the median of 36 sales is 16.9k PLN/m² because new buildings stand next door, while the 2013 estate with the offer sells at 12.3-15.4k. The same building would be best (RCN gives the building number), but only some listings know the building number, and only 3.5% of offers currently have 3 sales in the same building.
- **Previous sale.** When RCN has a sale of a unit within 150 m of the pin, with the same non-round area (±1%), the same number of rooms and a plausible price, dated before the listing was posted, the card shows "sold 2021 for 694k", most likely the current owner's purchase price. With three or more such sales (a block of identical apartments) nothing is shown. In Kraków this applies to about 10% of fresh offers.
- **Area.** The description is checked for a usable area smaller than in the parameters ("floor area 73 m², usable 37.82 m²"), sloped ceilings and floor-based area, and a basement or storage room included in the area.
- **Location.** `load_boundaries.py` loads city and municipality boundaries from PRG (GUGiK). For cities we check whether the pin lies in the city the listing states, and how far it is from the border. Flags: `pin_outside_city` (pin outside the city), `near_city_border` (closer than 1 km to the border; advertisers pin offers from outside the city to the last street on its side), `other_place_in_text` (the description mentions a nearby place outside the city, checked only up to 2.5 km from the border), `border_in_text` ("1 km from the Kraków border", "Zielonki municipality"), `lineage_city_mismatch` (another listing of the same unit gives a different town). The filter "Hide suspicious locations → recommended" hides the three strongest.
- **Developer price list.** Since 11 September 2025 every developer must publish daily on dane.gov.pl a price list of all units following the ministry template: development address, unit number, price per square metre and total with the effective date, prices of parking spaces, storage rooms and other mandatory fees. `load_developer_prices.py` walks the open API (`api.dane.gov.pl`, no key) of all institutions of type "developer" and their datasets, reads xlsx, csv, json and xml files (columns by name, because layouts differ; JSON and XML are flattened to one record per unit with the development address taken from parent objects, and a harvester XML that only points to daily CSV files leads to the file for the given day; the "prices" format without a town is skipped) and keeps the units whose town or municipality lies in the `RCN_CITIES` area with a margin. Some developers create a new dataset every day, so a unit is identified by institution and address, not by dataset. On first load it takes history roughly every 30 days back, then the newest file daily. Datasets without a new file for 45 days are skipped, and irrelevant ones are rechecked every 30 days. The signals match a listing to a unit by town, area (±0.05 m²) and street or price (±1%), and the number of rooms rules out mistakes. The listing price must not differ from every price of the unit in the price list by more than 15%, because the street alone mixes developments: Skanska's Awangarda offers on Mogilska were landing in the NOHO price list from the same street. The card shows "matches the developer price list" or "±X% vs developer price list", the first and the highest price of the unit in the price list, extras, and how many units of the development have disappeared from the price list (sold or reserved). A unit that is no longer in the price list while the listing is still up gets "disappeared from the developer price list".
- **Pin far from the street.** `load_osm.py` also fetches named streets from OpenStreetMap. When a listing gives a street and the nearest segment of a street with that name (compared by the last word, e.g. "Bogdanowskiego") is more than 1 km from the pin, it gets the `pin_far_from_street` flag. Distances to the border, roads and railways measured from the pin are then unreliable, and noise flags are not shown. Example: "94 m² with three balconies", Bogdanowskiego street, pin 34 m from the A4, while the street is 2 km from the motorway. Kraków estates ("os. Strusia") are areas, not streets, so they are skipped. In Kraków about 91% of offers with a street have the pin within 300 m of it.
- **Noisy surroundings.** `load_osm.py` fetches from OpenStreetMap (Overpass) motorways, expressways and trunk-standard national roads, railway lines and paved runways longer than 1800 m around the cities in `RCN_CITIES`. Tunnels are skipped. Flags: `near_expressway` (up to 300 m from the pin, with the road number, e.g. "S52 280 m"), `near_railway` (up to 150 m), `under_approach` (in line with a runway, up to 8 km from its end, in a corridor about 0.8-1.6 km wide). A pin can be off by a few hundred metres, so this is a signal to check, not a verdict: Zakątek in Modlnica has its pin 1046 m from the S52, while the building itself stands 525 m from it. The "Hide noisy surroundings" filter is in "History and market".

```bash
uv run python load_boundaries.py                    # boundaries from PRG, once (and after boundary changes)
uv run python load_transactions.py --city Kraków    # RCN transactions (the enricher does this itself when RCN_CITIES is set)
uv run python load_transactions.py --city Warszawa --city Wrocław --margin-km 10
uv run python load_osm.py --city Kraków             # streets, roads, railways and airports from OSM (enricher too, with RCN_CITIES)
uv run python load_developer_prices.py --city Kraków  # developer price lists from dane.gov.pl (enricher daily, with RCN_CITIES)
uv run python signals.py                            # recomputes the signals right away
```

- **Unchecked listings.** In production the scraper only refreshes the area from `docker-compose.yaml` (currently `--city=Kraków`), so listings outside it stay "active" forever. In October 2026 there were 195k of them, and the six "cheapest" ones around Kraków turned out to have been taken down since March-June. Search hides active listings not checked for more than 45 days by default (`hide_unchecked`, in the "History and market" filters), the card shows "not checked since …", and the signals treat them as ended at the last check. To also search around Kraków, add `--radius-km=15` to the scraper and enricher commands in `docker-compose.yaml` (otodom accepts 0, 5, 10, 15, 25, 50, 75). Search then gets `distanceRadius` (for Kraków and 15 km that's about 700 more listings), and the refresh pass and the enricher also take stored listings up to that distance from the city border (requires `load_boundaries.py`). The enricher will then evaluate more listings, so keep an eye on `ENRICHER_DAILY_BUDGET_USD`.

The enricher recomputes the signals by itself every `MARKET_SIGNALS_INTERVAL_HOURS` (default 6 h, 0 disables), at the start of a cycle. The whole run for ~275k listings takes a few minutes and uses up to about 1 GB of memory. The enricher runs it as a separate process (`signals.py`), so the memory is released afterwards and an error doesn't stop evaluations. If the server is too small, set `MARKET_SIGNALS_INTERVAL_HOURS=0` and run `signals.py` manually. The signals also go into the AI evaluation prompt and the assistant cards, but into existing template fields (`Adres`, `Data wystawienia`, `Dane rynkowe`), so stored evaluations are not invalidated. Only new evaluations and those recomputed for another reason get them.

Side note: otodom replaces the description and street of a taken-down listing with asterisks (`***`). Previously the scraper overwrote the stored data with that, and about 21k listings lost their description. Now masked values don't overwrite stored ones, and masked JSON doesn't overwrite the stored raw JSON.

## Temporary: repairing listings without a location

> **Temporary.** To be removed once there are no more active listings without a city in the database (`select count(*) from ads where status='active' and city_id is null`).

Since June 2026 otodom stopped sending the city, district, county and voivodeship in the old `address` field, so ~30k listings ended up in the database without a location. The scraper now reads it from the new place and repairs these listings by itself when re-fetching them, but at the normal pace that takes about a day. To speed it up, run a process that fetches only listings without a city. Ideally two, from different IPs (otodom blocks per address), splitting the work with `--shard`:

```bash
# on the VPS, next to the main container; --build builds the image from the current code in the repository directory
docker compose run --build --rm -d --name otodom-location-repair otodom-scrapper python main.py --no-scrape --update --only-missing-locations --max-price=0 --shard=1/2
docker logs -f otodom-location-repair

# on your own computer (local .env points to the same database)
uv run python main.py --no-scrape --update --only-missing-locations --max-price 0 --shard 2/2
```

- `--only-missing-locations` takes **all** active listings without a city, regardless of `--max-age-days` and `--city`, because without a city they can't be assigned to any. `--max-price 0` disables the price filter (default 1 million PLN).
- In this mode the order is reversed: first the listings the scraper most recently saw in search results. Those are mostly still-active offers. The ones not seen for weeks, almost always already taken down from otodom, go last and then get the taken-down status.
- `--shard 1/2` takes listings with an even ID, `--shard 2/2` with an odd one. Without splitting, two processes would mostly fetch the same listings, because each starts with the same list in the same order. It works for any number of processes (`1/3`, `2/3`, `3/3`), as long as each gets the same number after the slash.
- The process doesn't exit on its own (like every `main.py` run); it rechecks the queue every minute. Stop it (`docker stop otodom-location-repair` or Ctrl+C) when `Found 0 ads in DB to verify` appears in the log.
- Two processes from one IP mean twice as many requests to otodom and a higher risk of being blocked. The scraper waits it out (pause of 1 to 30 minutes), but if the logs show a lot of `Blocked by otodom`, increase `--request-delay`.
- All processes report as the same service, so the Status tab shows the state of whichever reported last, and the logs get mixed.
- The main scraper with `--no-scrape` doesn't collect new listings. If you change its command for the duration of the repair, restore it afterwards. Collection will catch up on skipped listings on the next pass through the result pages.

## Raw JSON and re-parsing

The scraper stores the last JSON of every fetched listing (compressed, 5-8 kB) in the `ad_raw_payloads` table. When it turns out the parser is missing something or otodom changed the format, you fix the parser and rebuild the data without re-fetching the pages:

```bash
uv run python reparse.py            # only counts what would change (listings without a city)
uv run python reparse.py --apply    # saves
uv run python reparse.py --all --apply --limit 1000
```

`--no-store-raw` in `main.py` disables storing.

## Diagnostics

```bash
# how much it cost and how many were evaluated
docker compose exec otodom-api python -c "
from database import DatabaseManager
from sqlalchemy import text
with DatabaseManager().get_session() as s:
    print(s.execute(text('''
        SELECT count(*) AS ocenione,
               round(sum(cost_usd)::numeric, 2) AS koszt_usd,
               round(avg(overall_score)::numeric, 2) AS srednia_ocena
        FROM ad_evaluations WHERE status = 'ok'
    ''')).mappings().one())
"
```

```sql
-- what was rejected at stage 1 and why
SELECT rejection_reason, count(*) FROM ad_screenings
WHERE status = 'rejected' GROUP BY 1 ORDER BY 2 DESC;

-- what failed
SELECT ad_id, attempts, left(error_message, 120) FROM ad_evaluations
WHERE status = 'failed' ORDER BY attempts DESC LIMIT 20;

-- clear failures so they are retried
DELETE FROM ad_screenings WHERE status = 'failed';
DELETE FROM ad_evaluations WHERE status = 'failed';

-- score distribution, i.e. whether the rubric is well calibrated
SELECT overall_score, count(*) FROM ad_evaluations
WHERE status = 'ok' GROUP BY 1 ORDER BY 1;
```

If in the last query almost everything sits at 7-8, the rubric in `evaluation_system.md` needs tightening - a search like that won't filter anything out.

## Tests

```bash
uv run python -m unittest discover -s tests -t .
```

They require neither a database nor an API key.
