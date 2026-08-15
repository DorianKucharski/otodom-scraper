# Otodom scraper + ocena AI + wyszukiwarka

Trzy niezależne procesy nad jedną bazą PostgreSQL (PostGIS + pg_trgm):

| Usługa | Co robi | Obraz |
| --- | --- | --- |
| `otodom-scrapper` | zbiera ogłoszenia z otodom.pl do bazy | `otodom-scraper:local` |
| `otodom-enricher` | ocenia zebrane ogłoszenia modelem LLM (zdjęcia + opis) | ten sam obraz, inna komenda |
| `otodom-api` | REST API + zbudowany frontend na `:8000` | `otodom-api:local` |

Enricher pisze wyłącznie do `ad_screenings` i `ad_evaluations`. Scraper ich nie dotyka, więc kolejny przebieg scrapera nie kasuje ocen.

## Uruchomienie od zera

```bash
cp .env.example .env
# uzupełnij DATABASE_URL i ANTHROPIC_API_KEY
docker compose up -d --build
```

Baza i widoki tworzą się same przy starcie scrapera i enrichera. Frontend jest pod `http://<host>:8000`, dokumentacja API pod `http://<host>:8000/docs`.

## Zawężanie zakresu

Parametry ustawia się w `command:` w `docker-compose.yaml`, osobno dla scrapera i osobno dla enrichera.

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

**Trzymaj oba zakresy zgodne.** Enricher ocenia tylko to, co scraper zebrał, więc szerszy enricher nic nie zmieni, a węższy zostawi część ogłoszeń bez ocen.

Nazwy lokalizacji można pisać z ogonkami i z wielkiej litery (`Kraków`, `Małopolskie`) albo jako slug otodomu (`krakow`, `malopolskie`) - obie usługi przyjmują jedno i drugie. `--district` wymaga `--city`, a `--city` wymaga `--voivodeship`.

### Wspólne flagi zakresu

| Flaga | Domyślnie | Uwaga |
| --- | --- | --- |
| `--voivodeship=` | brak (cała Polska) | |
| `--city=` | brak | wymaga `--voivodeship` |
| `--district=` | brak | wymaga `--city` |
| `--min-price=` / `--max-price=` | scraper `0` / `1000000`, enricher bez limitu | |
| `--houses` / `--no-houses` | włączone | |
| `--apartments` / `--no-apartments` | włączone | |
| `--sale` / `--no-sale` | włączone | |
| `--rent` / `--no-rent` | włączone | |

### Flagi tylko scrapera

| Flaga | Do czego |
| --- | --- |
| `--scrape` / `--no-scrape` | zbieranie nowych ogłoszeń |
| `--update` / `--no-update` | odświeżanie już zapisanych (cena, status) |

### Flagi tylko enrichera

| Flaga | Do czego |
| --- | --- |
| `--screen` / `--no-screen` | tani etap tekstowy (Haiku) |
| `--evaluate` / `--no-evaluate` | pełna ocena ze zdjęciami (Sonnet) |
| `--limit=N` | maksymalnie N ogłoszeń na etap w jednym cyklu - **tak ogranicza się koszt** |
| `--once` | jeden przebieg zamiast pętli |
| `--force` | ocenia od nowa, nawet gdy wynik jest aktualny |
| `--dry-run` | drukuje JSON, nic nie zapisuje |
| `--ad-url=` | jedno konkretne ogłoszenie |

Koszt przy domyślnych modelach to około 0,002 USD za ogłoszenie na etapie 1 i około 0,05 USD na etapie 2. Zanim puścisz na cały Kraków, ustaw `--limit=20` i zobacz w bazie, co wyszło.

## Codzienne komendy

```bash
# stan usług
docker compose ps

# logi na żywo
docker compose logs -f otodom-enricher
docker compose logs -f otodom-scrapper
docker compose logs --tail=200 otodom-api

# restart jednej usługi bez ruszania reszty
docker compose restart otodom-enricher

# zatrzymanie jednej usługi
docker compose stop otodom-scrapper

# tylko enricher (reszta wyłączona)
docker compose stop otodom-scrapper otodom-api
docker compose up -d otodom-enricher

# wszystko z powrotem
docker compose up -d
```

### Po zmianie parametrów w `command:`

Nie trzeba przebudowywać obrazu, bo `command` nie jest jego częścią:

```bash
docker compose up -d otodom-enricher
```

Compose zauważy zmianę konfiguracji i odtworzy sam kontener. `docker compose restart` **nie** wystarczy - restart odpala stary kontener ze starą komendą.

### Po zmianie `.env`

```bash
docker compose up -d
```

To samo co wyżej - zmienne środowiskowe wczytują się przy tworzeniu kontenera, nie przy restarcie.

### Po zmianie kodu lub promptów

```bash
docker compose up -d --build
```

Prompty (`enricher/prompts/`) są w obrazie, więc ich zmiana wymaga przebudowy. Uwaga: `prompt_version` to hash szablonu, więc **po zmianie promptu enricher oceni od nowa wszystkie ogłoszenia w swoim zakresie**. Przy szerokim zakresie to realny koszt - najpierw sprawdź nowy prompt na `--dry-run`, dopiero potem wdrażaj.

```bash
# przebudowa tylko jednego obrazu
docker compose build otodom-enricher && docker compose up -d otodom-enricher
```

## Iterowanie nad promptami

Najszybsza pętla nie wymaga Dockera ani bazy:

```bash
uv sync
uv run python enrich.py --ad-url "https://www.otodom.pl/pl/oferta/..." --dry-run
```

Drukuje wynik obu etapów jako JSON i nic nie zapisuje. Prompty edytujesz w `enricher/prompts/`:

- `screening_system.md` - kryteria odrzucenia na etapie 1
- `evaluation_system.md` - rubryka ocen 1-10 (to tu kalibrujesz, co znaczy 5, a co 8)
- `*_user.jinja2` - dane ogłoszenia wstawiane do promptu

## Kiedy enricher ocenia ogłoszenie ponownie

Sam z siebie nie powtarza pracy. Ponowna ocena leci tylko gdy:

- ogłoszenia jeszcze nie oceniono,
- zmieniła się treść (tytuł, opis, cechy, zdjęcia, metraż, pokoje, piętro, stan),
- zmienił się prompt (`prompt_version`),
- cena odjechała o więcej niż `EVALUATION_PRICE_DRIFT_THRESHOLD` (domyślnie 5%) od ceny z momentu oceny,
- poprzednia próba się wywaliła i nie przekroczyła jeszcze trzech podejść.

Przebieg `--update` scrapera, który tylko odświeża `modified_at`, nie kosztuje ani tokena.

## Konfiguracja modeli (`.env`)

| Zmienna | Domyślnie | Uwaga |
| --- | --- | --- |
| `LLM_PROVIDER` | `anthropic` | albo `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | - | brak = błąd przy starcie |
| `LLM_BASE_URL` | - | dla OpenRouter, vLLM, Ollama |
| `SCREENING_MODEL` | `claude-haiku-4-5` | |
| `EVALUATION_MODEL` | `claude-sonnet-5` | |
| `LLM_MAX_IMAGES` | `8` | główny czynnik kosztu etapu 2 |
| `LLM_DOWNLOAD_IMAGES` | `false` | patrz niżej - ustaw `true`, jeśli CDN otodomu blokuje API |
| `LLM_EFFORT` | `medium` | pomijany dla modeli, które go nie przyjmują (Haiku) |
| `EVALUATION_PRICE_DRIFT_THRESHOLD` | `0.05` | |
| `ENRICHER_CONCURRENCY` | `4` | równoległych ogłoszeń |
| `ENRICHER_CYCLE_PAUSE_SECONDS` | `300` | przerwa między cyklami |

## Zdjęcia: URL kontra pobieranie

Domyślnie do modelu lecą same adresy zdjęć, a pobiera je API dostawcy. CDN otodomu potrafi taki request odrzucić:

```
Unable to download the file. Please verify the URL and try again.
```

Enricher radzi sobie z tym sam: po pierwszym takim błędzie pobiera zdjęcia przez `cloudscraper` (tak samo jak scraper) i wysyła je jako base64, a kolejne ogłoszenia w tym procesie idą od razu tą drogą. W logu zobaczysz:

```
The API could not reach the image URLs of ad 68006816, downloading images from now on.
```

Ten jeden nieudany request powtarza się po każdym restarcie kontenera. Żeby go uniknąć, ustaw w `.env`:

```
LLM_DOWNLOAD_IMAGES=true
```

Kosztem jest pobranie kilku zdjęć na ogłoszenie po stronie enrichera, czyli trochę ruchu i czasu, ale zero dodatkowych tokenów.

## Diagnostyka

```bash
# ile kosztowało i ile ocenione
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
-- co odpadło na etapie 1 i dlaczego
SELECT rejection_reason, count(*) FROM ad_screenings
WHERE status = 'rejected' GROUP BY 1 ORDER BY 2 DESC;

-- co się wywaliło
SELECT ad_id, attempts, left(error_message, 120) FROM ad_evaluations
WHERE status = 'failed' ORDER BY attempts DESC LIMIT 20;

-- wyczyszczenie błędów do ponowienia
DELETE FROM ad_screenings WHERE status = 'failed';
DELETE FROM ad_evaluations WHERE status = 'failed';

-- rozkład ocen, czyli czy rubryka jest dobrze skalibrowana
SELECT overall_score, count(*) FROM ad_evaluations
WHERE status = 'ok' GROUP BY 1 ORDER BY 1;
```

Jeśli w ostatnim zapytaniu prawie wszystko siedzi na 7-8, rubryka w `evaluation_system.md` wymaga zaostrzenia - taka wyszukiwarka niczego nie odsieje.

## Testy

```bash
uv run python -m unittest discover -s tests -t .
```

Nie wymagają bazy ani klucza API.
