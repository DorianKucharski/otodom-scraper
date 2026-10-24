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
| `--max-age-days=` | po ilu dniach od ostatniego sprawdzenia ogłoszenie jest odświeżane (domyślnie `30`, `0` = zawsze) |
| `--request-delay=` | minimalna przerwa między zapytaniami do otodom w sekundach, plus do 50% losowo (domyślnie `2`) |

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

## Koszty

Zmierzone dla domyślnych modeli i ośmiu zdjęć w wariancie `medium` (655x491, ~429 tokenów każde):

| Etap | Wejście | Wyjście | Koszt za ogłoszenie |
| --- | --- | --- | --- |
| Przesiew (Haiku 4.5) | ~2 600 tok. | ~250 tok. | **~0,004 USD** |
| Ocena (Sonnet 5) | ~6 500 tok. | ~600 tok. | **~0,029 USD** |

Z tego zdjęcia to 3 400 tokenów, czyli ponad połowa wejścia oceny, a odpowiedź modelu to około jedna trzecia całego kosztu i nie zależy od liczby zdjęć.

**Skala ma znaczenie większe niż cokolwiek innego.** Kraków do 2 mln zł to blisko 20 tys. ogłoszeń, czyli około 80 USD samego przesiewu i około 500 USD ocen. Zawężaj filtrami, zanim zaczniesz kręcić gałkami modeli.

### Co realnie obniża rachunek

| Zmiana | Oszczędność | Koszt zmiany |
| --- | --- | --- |
| Węższe filtry (dzielnica, wąskie widełki cen, `--no-rent`) | proporcjonalna do liczby ogłoszeń | brak, to zwykle i tak jest to, czego szukasz |
| `ENRICHER_DAILY_BUDGET_USD` (domyślnie 10) | twardy sufit dobowy, sprawdzany przed każdym ogłoszeniem | ocenianie rozkłada się na dni |
| `LLM_MAX_IMAGES=5` | ~13% kosztu oceny | mniej materiału na `photo_trust_score` |
| `LLM_IMAGE_VARIANT=small` | ~30% kosztu oceny | 314x236 nie wystarcza, by ocenić jakość wykończenia |
| `LLM_MAX_DESCRIPTION_CHARACTERS=2000` | ~8% kosztu oceny, ~25% przesiewu | dłuższe opisy tracą końcówkę |
| `EVALUATION_MODEL=claude-haiku-4-5` | ~65% kosztu oceny | wyraźnie słabsza ocena zdjęć, czyli to, po co to narzędzie powstało |

### Czy przesiew się opłaca

Przesiew kosztuje 0,004 USD i oszczędza 0,029 USD na każdym odrzuconym ogłoszeniu, więc zwraca się dopiero przy odrzucaniu ponad 14 procent. Sprawdź swoją stopę:

```sql
SELECT status, count(*), round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS procent
FROM ad_screenings GROUP BY status;
```

Jeśli odrzuconych jest mniej niż 14 procent, przesiew dokłada do rachunku zamiast go zbijać i lepiej wyłączyć go przez `--no-screen`. Jedyne, co wtedy tracisz, to `extracted_attributes` wyciągane z opisu.

Zanim puścisz na szeroki zakres, ustaw `--limit=20` i zobacz w bazie, co wyszło.

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

## Logowanie

Ustaw `APP_PASSWORD` w `.env` i zrestartuj `otodom-api`. Bez tej zmiennej API jest otwarte dla każdego, kto trafi na port (w logu pojawi się ostrzeżenie).

- Jedno hasło dla wszystkich, a przy logowaniu wpisuje się imię. Trafia ono do historii statusów, więc widać, kto co zmienił.
- Ciasteczko jest ważne rok, więc na każdym urządzeniu logujesz się raz.
- Zmiana `APP_PASSWORD` wylogowuje wszystkie urządzenia, bo ciasteczko jest nim podpisane.
- Chronione jest całe `/api` (także logi usług) oraz `/docs`. Sam zbudowany frontend jest publiczny, ale bez sesji pokazuje tylko ekran logowania.
- **HTTPS daje domena od Mikrusa** (`https://steve138-30138.wykr.es`, przez Cloudflare). Goły port `:30138` i `http://` na tej domenie nadal działają bez szyfrowania. Dlatego ustaw `APP_PUBLIC_URL=https://steve138-30138.wykr.es`: każde zapytanie, które nie przyszło po HTTPS, dostaje przekierowanie 308 na ten adres, więc formularz logowania nigdy nie wyświetli się po HTTP. Wyjątkiem jest `/api/health`.
- O tym, czy połączenie było szyfrowane, API wnioskuje z nagłówka `X-Forwarded-Proto` od Cloudflare. Na tej podstawie ciasteczko dostaje też flagę `Secure`.

## Moje mieszkania

Każde ogłoszenie można zapisać ze statusem z panelu szczegółów. Każda zmiana statusu i każda notatka to osobny wpis w historii z komentarzem, autorem i datą (`ad_tracking_events`). Bieżący stan leży w `ad_tracking`.

| Status | Znaczenie |
|---|---|
| Do sprawdzenia | wpadło w oko, trzeba się przyjrzeć |
| Do zadzwonienia | warte kontaktu |
| Po kontakcie | czekam: oddzwonią, wyślą zdjęcia, nie odebrał |
| Umówione oglądanie | wymaga daty i godziny |
| Obejrzane | po wizycie, opcjonalna ocena 1-5 |
| Faworyt | poważny kandydat po obejrzeniu |
| Negocjacje / oferta | opcjonalna kwota oferty |
| Wybrane | koniec poszukiwań |
| Odrzucone | rezygnuję, powód w komentarzu |
| Niedostępne | sprzedane, wynajęte, wycofane |

Przejścia są dowolne. Wyszukiwarka domyślnie ukrywa odrzucone i niedostępne, a w sekcji filtrów "Moje statusy" można to wyłączyć albo pokazać tylko wybrane statusy. Zakładka **Moje mieszkania** grupuje zapisane ogłoszenia po statusie, a nad nimi pokazuje listę umówionych oglądań. Przy każdym zapisanym ogłoszeniu widać zmianę ceny od chwili zapisania.

Tabele tworzą się przy starcie scrapera albo enrichera, jak wszystkie inne. `drop_tables()` w `main.py` kasuje także je.

## Asystent AI

Nad listą wyników w zakładce **Wyszukiwarka** jest pole „Zapytaj asystenta”. Wpisujesz po ludzku, czego szukasz („jasne 3 pokoje w Krakowie do 950 tys., blisko zieleni, nie parter”), a asystent działa w dwóch krokach:

1. **Rozumienie** (`ASSISTANT_INTERPRET_MODEL`, domyślnie Haiku, 0,005-0,01 USD, 5-7 s) zamienia wiadomość na zwykłe filtry po lewej (miasto, dzielnica albo okolica punktu, cena, metraż, pokoje, piętro), słowa kluczowe do opisów i listę miękkich kryteriów („musi: jasne wnętrze”, „mile widziane: blisko zieleni”). Filtry widzisz i możesz poprawić. Miękkie rzeczy celowo nie są filtrami, bo połowa ogłoszeń ich nie zaznacza.
2. **Ranking** (`ASSISTANT_RANK_MODEL`, domyślnie Sonnet 5, zmierzone 0,11 USD i 31 s dla 30 ogłoszeń bez ocen, do około 0,20 USD, gdy wszystkie mają ocenę ze zdjęć) bierze `ASSISTANT_CANDIDATES` (30) ogłoszeń spełniających filtry, w kolejności po trafieniach słów kluczowych i ocenie AI. Czyta ich dane, fakty z przesiewu, ocenę ze zdjęć i początek opisu, a potem wybiera najwyżej 10 z oceną dopasowania, uzasadnieniem i listą rzeczy niespełnionych albo niepewnych.

„Pod Warszawą” czy „okolice Krakowa” to promień 20-40 km od centrum, bez filtra miasta, więc łapie też ogłoszenia, które mają tylko współrzędne. Kolejna wiadomość w tej samej rozmowie („taniej”, „a może Dębniki”) poprawia poprzednie ustawienia, zamiast zaczynać od zera. Po ręcznej zmianie filtrów „Przelicz ranking” ocenia od nowa z tymi filtrami.

**Oceń ze zdjęć**: większość ogłoszeń poza zakresem enrichera nie ma oceny ze zdjęć, więc ranking opiera się wtedy tylko na tekście. Przycisk dopisuje je do kolejki `ad_evaluation_requests`. Enricher sprawdza ją co 10 s w osobnym wątku, robi przesiew i pełną ocenę bez względu na swoje filtry `--city` i `--max-price`, a wynik zapisuje w bazie jak każdą inną ocenę. Po zakończeniu pojawia się „Przelicz z nowymi ocenami”. Działa tylko wtedy, gdy kontener enrichera chodzi w pętli.

| Zmienna | Domyślnie | Uwaga |
| --- | --- | --- |
| `ASSISTANT_DAILY_BUDGET_USD` | `2` | suma kosztów asystenta z 24 h (`assistant_calls`), po przekroczeniu API zwraca 429 |
| `ENRICHER_REQUEST_DAILY_BUDGET_USD` | `3` | osobny limit na oceny na żądanie, niezależny od `ENRICHER_DAILY_BUDGET_USD` |
| `ASSISTANT_INTERPRET_MODEL` | `claude-haiku-4-5` | |
| `ASSISTANT_RANK_MODEL` | `claude-sonnet-5` | |
| `ASSISTANT_RANK_EFFORT` | `low` | wyższy wydłuża odpowiedź, a Cloudflare zrywa połączenie po 100 s |
| `ASSISTANT_CANDIDATES` | `30` | więcej kandydatów to proporcjonalnie droższy ranking |
| `ASSISTANT_DESCRIPTION_CHARACTERS` | `800` | ile opisu trafia do rankingu na ogłoszenie |

Asystent używa tego samego klucza co enricher (`ANTHROPIC_API_KEY`), więc kontener `otodom-api` musi go mieć w `.env`. Bez klucza panel pokazuje, że asystent jest wyłączony. Każde wywołanie, z żądaniem, odpowiedzią i kosztem, jest w tabeli `assistant_calls`.

## Podgląd statusu i logów

UI ma trzy zakładki: **Wyszukiwarka**, **Moje mieszkania** i **Status**. Zakładka Status pokazuje:

- lampkę i stan każdej usługi (Pracuje / Czeka / Brak sygnału / Zatrzymany), aktualny etap, czas od ostatniego sygnału, czas działania, statystyki ostatniego cyklu i komendę, z jaką proces wystartował,
- logi obu usług, przełączane zakładkami, z filtrem poziomu, wyszukiwaniem po treści i wyborem liczby linii (200-2000).

Nie wymaga to dostępu do gniazda Dockera. Scraper i enricher zapisują sygnał życia do tabeli `service_heartbeats`, a swoje logi do `service_logs`, skąd API je czyta. Dzięki temu podgląd działa też przy uruchomieniu spoza kontenerów.

- Wątek w tle odświeża sygnał co 30 s, więc długi przebieg scrapowania nie wygląda na zawieszenie. Brak sygnału przez ponad 3 minuty oznacza zatrzymany albo zawieszony proces.
- `service_logs` to bufor cykliczny: trzymane jest ostatnie 2000 linii na usługę, starsze są kasowane. Baza nie rośnie w nieskończoność.
- Zapis logów nie może wywrócić procesu: przy błędzie bazy handler zrzuca komunikat na stderr i wstrzymuje zapisy na minutę.
- `--dry-run` w enricherze nie zapisuje ani logów, ani sygnału życia.

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

## Historia ogłoszeń, ceny w okolicy i podejrzane lokalizacje

Każde ogłoszenie dostaje w tabeli `ad_market_signals` zestaw sygnałów liczonych bez LLM. Wyszukiwarka pokazuje je jako znaczniki na kartach (najechanie myszką pokazuje szczegóły), w sekcji „Historia ogłoszenia i rynek” w szczegółach i w filtrach „Historia i rynek”.

- **Ten sam lokal w kolejnych ogłoszeniach.** Agencje zdejmują ogłoszenie i wystawiają je od nowa co kilka tygodni, żeby wyglądało na świeże. Właściciel najpierw sprzedaje sam, potem oddaje lokal agencji, która podnosi cenę. Scraper łączy takie ogłoszenia w jeden „rodowód” po metrażu (z dokładnością do 0,5%), pokojach, piętrze, roku budowy, odległości (do 3 km, bo agencje przesuwają pinezki) i podobieństwie tytułu lub opisu. Dwa ogłoszenia wiszące jednocześnie łączy tylko wtedy, gdy to ten sam ogłoszeniodawca, ta sama cena i prawie ten sam tekst, więc identyczne lokale z jednej inwestycji zostają osobno. Z rodowodu wychodzi **czas na rynku** liczony od pierwszego ogłoszenia, liczba ogłoszeń i ogłoszeniodawców oraz pierwsza, najniższa i najwyższa znana cena.
- **Historia cen.** Od tej wersji scraper zapisuje w `ad_price_observations` każdą zmianę ceny, metrażu i statusu. Starsze ogłoszenia mają jedną obserwację z ostatniego pobrania, więc pełna historia cen narasta od teraz.
- **Podobne oferty w okolicy.** Zamiast mediany całej dzielnicy: mediana ceny za metr z co najmniej 10 podobnych ofert (ten sam typ, metraż ±35%, aktywne albo zdjęte w ostatnim półroczu, każdy lokal raz) w promieniu od 750 m do 10 km od pinezki. Mediana dzielnicy myliła, bo duży metraż ma niższą cenę za metr, a pinezka mogła wskazywać inną dzielnicę niż faktyczne położenie.
- **Ceny transakcyjne z RCN.** `load_transactions.py` ściąga z Rejestru Cen Nieruchomości (otwarty WFS GUGiK) sprzedaże lokali wokół wskazanych miast. Sygnały porównują cenę za metr z medianą prawdziwych transakcji z ostatnich 2 lat (ten sam rynek, gdy jest ich dość, metraż ±35%, cały lokal, wolny rynek). To jedyne porównanie, w którym nie ma cen ofertowych.
- **Lokalizacja.** `load_boundaries.py` wczytuje granice miast i gmin z PRG (GUGiK). Dla miast sprawdzamy, czy pinezka leży w mieście, które podaje ogłoszenie, i jak daleko jest od granicy. Flagi: `pin_outside_city` (pinezka poza miastem), `near_city_border` (bliżej niż 1 km od granicy, ogłoszeniodawcy przypinają oferty spod miasta do ostatniej ulicy po jego stronie), `other_place_in_text` (opis wymienia miejscowość z okolicy spoza miasta, sprawdzane tylko do 2,5 km od granicy), `border_in_text` („1 km od granicy Krakowa”, „gmina Zielonki”), `lineage_city_mismatch` (inne ogłoszenie tego samego lokalu podaje inną miejscowość). Filtr „Ukryj podejrzane lokalizacje → zalecane” chowa trzy najmocniejsze.

```bash
uv run python load_boundaries.py                    # granice z PRG, raz (i po zmianach granic)
uv run python load_transactions.py --city Kraków    # transakcje RCN, np. raz w miesiącu
uv run python load_transactions.py --city Warszawa --city Wrocław --margin-km 10
uv run python signals.py                            # przelicza sygnały od razu
```

- **Niesprawdzane ogłoszenia.** Scraper na produkcji odświeża tylko obszar z `docker-compose.yaml` (dziś `--city=Kraków`), więc ogłoszenia spoza niego zostają „aktywne” na zawsze. W październiku 2026 było takich 195 tys., a sześć „najtańszych” z okolic Krakowa okazało się zdjętych od marca–czerwca. Wyszukiwarka domyślnie ukrywa aktywne ogłoszenia niesprawdzane od ponad 45 dni (`hide_unchecked`, w filtrach „Historia i rynek”), karta pokazuje „niesprawdzane od …”, a sygnały traktują je jak zakończone przy ostatnim sprawdzeniu. Żeby szukać poza Krakowem, trzeba uruchomić dodatkowy scraper dla tego obszaru.

Enricher przelicza sygnały sam co `MARKET_SIGNALS_INTERVAL_HOURS` (domyślnie 6 h, 0 wyłącza), na początku cyklu. Całość dla ~275 tys. ogłoszeń trwa kilka minut. Sygnały trafiają też do promptu oceny AI i kart asystenta, ale do istniejących pól szablonu (`Adres`, `Data wystawienia`, `Dane rynkowe`), więc zapisane oceny nie unieważniają się. Dostaną je dopiero nowe oceny i te, które się przeliczą z innego powodu.

Przy okazji: otodom zastępuje opis i ulicę zdjętego ogłoszenia gwiazdkami (`***`). Wcześniej scraper nadpisywał tym zapisane dane i ok. 21 tys. ogłoszeń straciło opis. Teraz zamaskowane wartości nie nadpisują zapisanych, a zamaskowany JSON nie nadpisuje zapisanego surowego JSON-a.

## Tymczasowo: naprawa ogłoszeń bez lokalizacji

> **Tymczasowe.** Do usunięcia, gdy w bazie nie będzie już aktywnych ogłoszeń bez miasta (`select count(*) from ads where status='active' and city_id is null`).

Od czerwca 2026 otodom przestał wysyłać miasto, dzielnicę, powiat i województwo w starym polu `address`, więc ~30 tys. ogłoszeń trafiło do bazy bez lokalizacji. Scraper czyta ją już z nowego miejsca i sam naprawia te ogłoszenia przy ponownym pobraniu, ale przy zwykłym tempie trwa to około doby. Żeby to przyspieszyć, uruchom proces, który pobiera wyłącznie ogłoszenia bez miasta. Najlepiej dwa, z różnych IP (otodom blokuje per adres), z podziałem pracy przez `--shard`:

```bash
# na VPS-ie, obok głównego kontenera; --build buduje obraz z bieżącego kodu w katalogu repozytorium
docker compose run --build --rm -d --name otodom-location-repair otodom-scrapper python main.py --no-scrape --update --only-missing-locations --max-price=0 --shard=1/2
docker logs -f otodom-location-repair

# na własnym komputerze (lokalny .env wskazuje na tę samą bazę)
uv run python main.py --no-scrape --update --only-missing-locations --max-price 0 --shard 2/2
```

- `--only-missing-locations` bierze **wszystkie** aktywne ogłoszenia bez miasta, bez względu na `--max-age-days` i `--city`, bo bez miasta nie da się ich przypisać do żadnego. `--max-price 0` wyłącza filtr ceny (domyślnie 1 mln zł).
- W tym trybie kolejność jest odwrócona: najpierw ogłoszenia, które scraper widział ostatnio w wynikach wyszukiwania. To głównie wciąż aktywne oferty. Te niewidziane od tygodni, prawie zawsze już zdjęte z otodom, idą na koniec i dostają wtedy status zdjętego.
- `--shard 1/2` bierze ogłoszenia o parzystym ID, `--shard 2/2` o nieparzystym. Bez podziału dwa procesy pobierałyby w większości te same ogłoszenia, bo każdy na starcie bierze tę samą listę w tej samej kolejności. Działa dla dowolnej liczby procesów (`1/3`, `2/3`, `3/3`), byle każdy dostał tę samą liczbę po ukośniku.
- Proces nie kończy się sam (jak każdy przebieg `main.py`), tylko co minutę sprawdza kolejkę od nowa. Zatrzymaj go (`docker stop otodom-location-repair` albo Ctrl+C), gdy w logu pojawi się `Found 0 ads in DB to verify`.
- Dwa procesy z jednego IP to dwa razy więcej zapytań do otodom i większe ryzyko blokady. Scraper je przeczeka (pauza od 1 do 30 minut), ale jeśli w logach jest dużo `Blocked by otodom`, zwiększ `--request-delay`.
- Wszystkie procesy raportują się jako ta sama usługa, więc zakładka Status pokazuje stan tego, który zgłosił się ostatnio, a logi się mieszają.
- Główny scraper z `--no-scrape` nie zbiera nowych ogłoszeń. Jeśli na czas naprawy zmieniasz jego komendę, przywróć ją potem. Zbieranie nadrobi pominięte ogłoszenia przy następnym przejściu stron wyników.

## Surowe JSON-y i ponowne parsowanie

Scraper zapisuje ostatni JSON każdego pobranego ogłoszenia (skompresowany, 5-8 kB) w tabeli `ad_raw_payloads`. Gdy okaże się, że parser coś gubi albo otodom zmienił format, poprawia się parser i odtwarza dane bez ponownego pobierania stron:

```bash
uv run python reparse.py            # tylko liczy, co by się zmieniło (ogłoszenia bez miasta)
uv run python reparse.py --apply    # zapisuje
uv run python reparse.py --all --apply --limit 1000
```

`--no-store-raw` w `main.py` wyłącza zapisywanie.

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
