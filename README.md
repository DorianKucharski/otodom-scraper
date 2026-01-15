# Otodom Scraper

Scraper do pobierania danych z Otodom.pl i zapisywania ich w znormalizowanej bazie PostgreSQL z zaawansowanymi możliwościami wyszukiwania i analizy.

**📚 Quick Links:**
- [Instalacja](INSTALL.md) - Szczegółowa instrukcja instalacji
- [Quick Start](QUICKSTART.md) - 5-minutowy start
- [Przykłady](examples.py) - Zaawansowane przykłady zapytań
- [Podsumowanie](SUMMARY.md) - Krótkie podsumowanie projektu

## Funkcjonalności

- Scraping ogłoszeń z Otodom.pl
- Parsowanie danych do strukturowanych obiektów Python
- Zapis do znormalizowanej bazy PostgreSQL 17
- **Zaawansowane wyszukiwanie:**
  - Sortowanie ogłoszeń po liczbie cech (od największej do najmniejszej)
  - Wyszukiwanie geograficzne (ogłoszenia w promieniu X metrów)
  - Analiza zagęszczenia ofert w okolicy
  - Statystyki cenowe (średnie ceny, ceny/m², min/max)
  - Filtrowanie po dowolnych parametrach
- Indeksy PostgreSQL dla szybkich zapytań
- Wsparcie dla PostGIS (zapytania geograficzne)
- Wbudowane widoki analityczne

## Struktura projektu

```
otodom-scrapper/
├── scraper.py          # Moduł do pobierania danych ze stron Otodom
├── parser.py           # Parser HTML -> Python dataclasses
├── models.py           # SQLAlchemy ORM models (definicje tabel)
├── database.py         # DatabaseManager - zarządzanie bazą danych
├── main.py             # Główny skrypt aplikacji z przykładami
├── examples.py         # Zaawansowane przykłady zapytań ORM
├── alembic/            # Migracje bazy danych
│   ├── env.py
│   ├── script.py.mako
│   └── versions/       # Wersje migracji
├── alembic.ini         # Konfiguracja Alembic
├── requirements.txt    # Zależności Python
├── .env.example        # Przykładowa konfiguracja
└── README.md           # Ten plik
```

## Schemat bazy danych

Baza została zaprojektowana z myślą o:
- **Normalizacji** - brak duplikacji danych
- **Wydajności** - indeksy dla wszystkich ważnych kolumn
- **Analityce** - widoki i funkcje do raportowania
- **Geolokalizacji** - PostGIS dla zapytań przestrzennych

### Główne tabele:

- `ads` - Główna tabela z ogłoszeniami
- `provinces`, `counties`, `cities`, `districts` - Słowniki lokalizacji
- `owners` - Właściciele/agencje
- `ad_images` - Zdjęcia ogłoszeń
- `ad_features` - Cechy (lista)
- `ad_characteristics` - Charakterystyki (key-value)
- `ad_flat_equipment` - Wyposażenie mieszkania
- `ad_flat_areas` - Powierzchnie dodatkowe (balkon, piwnica)
- `ad_building_*` - Właściwości budynku

### Widoki analityczne:

- `vw_ads_by_city` - Statystyki ogłoszeń per miasto
- `vw_ads_by_district` - Statystyki ogłoszeń per dzielnica
- `vw_ads_with_feature_count` - Ogłoszenia z licznikami cech
- `vw_ads_detailed` - Pełne informacje o ogłoszeniu

### Funkcje:

- `get_ads_within_radius(lat, lon, radius)` - Ogłoszenia w promieniu
- `get_ad_density_in_area(lat, lon, radius)` - Zagęszczenie ofert

## Instalacja

### 1. Wymagania

- Python 3.10+
- PostgreSQL 17 (lub 13+)
- Rozszerzenia PostgreSQL: `postgis`, `pg_trgm`

### 2. Instalacja zależności Python

```bash
pip install -r requirements.txt
```

### 3. Konfiguracja PostgreSQL

#### Instalacja PostgreSQL i PostGIS

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql-17 postgresql-17-postgis-3
```

**macOS (Homebrew):**
```bash
brew install postgresql@17 postgis
```

**Windows:**
- Pobierz installer z [postgresql.org](https://www.postgresql.org/download/windows/)
- Podczas instalacji zaznacz PostGIS w Stack Builder

#### Utworzenie bazy danych

```bash
# Zaloguj się jako postgres
psql -U postgres

# W konsoli PostgreSQL:
CREATE DATABASE otodom_db;
CREATE USER otodom_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE otodom_db TO otodom_user;

# Wyjdź z psql
\q
```

#### Inicjalizacja schematu bazy (SQLAlchemy + Alembic)

**Opcja A: Użyj Alembic migrations (zalecane)**

```bash
# Wygeneruj początkową migrację
alembic revision --autogenerate -m "Initial migration"

# Zastosuj migrację
alembic upgrade head
```

**Opcja B: Utwórz tabele bezpośrednio z modeli**

W `main.py` odkomentuj:
```python
db_manager.create_all_tables()
```

### 4. Konfiguracja aplikacji

Skopiuj `.env.example` do `.env` i uzupełnij danymi dostępowymi:

```bash
cp .env.example .env
```

Edytuj `.env`:
```bash
DATABASE_URL=postgresql://otodom_user:your_password@localhost:5432/otodom_db
```

## Użycie

### Podstawowe użycie

```python
from scraper import Scraper
from parser import OtodomParser
from database import DatabaseManager
import os

# Inicjalizacja
db = DatabaseManager(os.getenv('DATABASE_URL'))
scraper = Scraper()
parser = OtodomParser()

# Scraping i zapis
url = "https://www.otodom.pl/pl/oferta/..."
raw_data = scraper.scrape(url)
ad = parser.parse(raw_data)
db.save_ad(ad)  # Automatyczny UPSERT

# Dostęp do modeli ORM
from models import Ad, City
with db.get_session() as session:
    # Zapytanie ORM
    ads = session.query(Ad).filter(Ad.city_id == '190').limit(10).all()
    for ad in ads:
        print(f"{ad.title}: {ad.price_value} PLN")
```

### Uruchomienie przykładowej aplikacji

```bash
python main.py
```

### Zaawansowane zapytania

#### 1. Sortowanie po liczbie cech

```python
# Ogłoszenia z największą liczbą cech
ads = db.get_ads_sorted_by_feature_count(
    city_id='190',  # Lublin
    min_features=5,
    limit=20
)

for ad in ads:
    print(f"{ad['title']}: {ad['features_count']} cech")
```

#### 2. Wyszukiwanie geograficzne

```python
# Ogłoszenia w promieniu 1km
nearby_ads = db.get_ads_within_radius(
    latitude=51.2465,
    longitude=22.5684,
    radius_meters=1000
)

for ad in nearby_ads:
    print(f"{ad['title']}: {ad['distance_meters']:.0f}m")
```

#### 3. Analiza zagęszczenia

```python
# Zagęszczenie ofert w okolicy
density = db.get_ad_density_stats(
    latitude=51.2465,
    longitude=22.5684,
    radius_meters=2000
)

print(f"Ofert: {density['ad_count']}")
print(f"Zagęszczenie: {density['density_per_km2']:.2f} ofert/km²")
print(f"Średnia cena: {density['avg_price']:,} PLN")
```

#### 4. Statystyki miasta

```python
stats = db.get_city_statistics('Lublin')
print(f"Liczba ofert: {stats['ad_count']}")
print(f"Średnia cena: {stats['avg_price']:,} PLN")
print(f"Średnia cena/m²: {stats['avg_price_per_m2']:,} PLN")
```

### Bezpośrednie zapytania SQL

Możesz też używać bezpośrednio SQL:

```sql
-- Top 10 najtańszych mieszkań w Lublinie
SELECT title, price_value, price_per_m2, area_value
FROM vw_ads_detailed
WHERE city_name = 'Lublin'
    AND status = 'active'
    AND property_type = 'FLAT'
ORDER BY price_value ASC
LIMIT 10;

-- Średnie ceny per dzielnica
SELECT
    district_name,
    ad_count,
    avg_price,
    avg_price_per_m2
FROM vw_ads_by_district
WHERE city_name = 'Lublin'
ORDER BY avg_price DESC;

-- Mieszkania z więcej niż 10 cechami
SELECT
    a.title,
    a.price_value,
    COUNT(DISTINCT f.feature) as feature_count
FROM ads a
JOIN ad_features f ON a.id = f.ad_id
GROUP BY a.id, a.title, a.price_value
HAVING COUNT(DISTINCT f.feature) > 10
ORDER BY feature_count DESC;

-- Zagęszczenie ofert w promieniu 1km od punktu
SELECT * FROM get_ad_density_in_area(51.2465, 22.5684, 1000);
```

## Przykładowe zapytania dla wyszukiwarki

### 1. Filtrowanie z sortowaniem po cechach

```sql
SELECT
    a.id,
    a.title,
    a.price_value,
    a.price_per_m2,
    COUNT(DISTINCT af.feature) as features_count,
    COUNT(DISTINCT ae.equipment) as equipment_count
FROM ads a
LEFT JOIN ad_features af ON a.id = af.ad_id
LEFT JOIN ad_flat_equipment ae ON a.id = ae.ad_id
WHERE
    a.city_id = '190'  -- Lublin
    AND a.flat_number_of_rooms = 2
    AND a.price_value BETWEEN 300000 AND 500000
    AND a.area_value BETWEEN 35 AND 50
    AND a.status = 'active'
GROUP BY a.id
ORDER BY features_count DESC, equipment_count DESC
LIMIT 20;
```

### 2. Wyszukiwanie z filtrem na cechy

```sql
-- Mieszkania z windą i balkonem
SELECT DISTINCT a.*
FROM ads a
JOIN ad_features af1 ON a.id = af1.ad_id AND af1.feature = 'winda'
JOIN ad_features af2 ON a.id = af2.ad_id AND af2.feature = 'balkon'
WHERE a.status = 'active'
ORDER BY a.price_value;
```

### 3. Mapa cieplna cen (heatmap)

```sql
-- Średnia cena w gridzie 0.01° (ok. 1km)
SELECT
    ROUND(latitude, 2) as lat_grid,
    ROUND(longitude, 2) as lon_grid,
    COUNT(*) as ad_count,
    AVG(price_value) as avg_price,
    AVG(price_per_m2) as avg_price_per_m2
FROM ads
WHERE status = 'active'
    AND city_id = '190'
GROUP BY lat_grid, lon_grid
HAVING COUNT(*) >= 3
ORDER BY avg_price DESC;
```

## SQLAlchemy ORM i Alembic

### Zalety SQLAlchemy ORM

- **Type Safety**: Automatyczne sprawdzanie typów w IDE
- **Relacje**: Łatwy dostęp do powiązanych obiektów (ad.city.name)
- **Migracje**: Automatyczne generowanie migracji przez Alembic
- **Czytelność**: Kod Pythonowy zamiast SQL
- **Bezpieczeństwo**: Ochrona przed SQL injection

### Praca z migracjami Alembic

```bash
# Generowanie nowej migracji po zmianie modeli
alembic revision --autogenerate -m "Add new field to Ad"

# Zastosowanie migracji
alembic upgrade head

# Cofnięcie ostatniej migracji
alembic downgrade -1

# Historia migracji
alembic history

# Aktualna wersja bazy
alembic current
```

### Przykłady zapytań ORM

```python
from models import Ad, City, AdFeature
from sqlalchemy import select, func

with db.get_session() as session:
    # Podstawowe zapytanie
    ads = session.query(Ad).filter(
        Ad.price_value.between(300000, 500000),
        Ad.flat_number_of_rooms == 2
    ).all()

    # Zapytanie z joinami
    ads_with_city = session.query(Ad, City).join(City).filter(
        City.name == 'Lublin'
    ).all()

    # Zapytanie agregujące
    avg_price = session.query(func.avg(Ad.price_value)).filter(
        Ad.city_id == '190'
    ).scalar()

    # Relacje (lazy loading)
    ad = session.get(Ad, 67537414)
    print(ad.city.name)  # Automatyczny JOIN
    print([f.feature for f in ad.features])  # Lista cech

    # Advanced: subquery
    subq = select(AdFeature.ad_id).where(AdFeature.feature == 'balkon')
    ads_with_balcony = session.query(Ad).filter(Ad.id.in_(subq)).all()
```

## Rozszerzanie funkcjonalności

### Dodawanie nowych pól do modeli

1. Edytuj `models.py` i dodaj nowe pole:
```python
class Ad(Base):
    # ... existing fields ...
    new_field: Mapped[Optional[str]] = mapped_column(String(100))
```

2. Wygeneruj migrację:
```bash
alembic revision --autogenerate -m "Add new_field to Ad"
```

3. Zastosuj migrację:
```bash
alembic upgrade head
```

### Dodawanie nowych zapytań

Dodaj metody do klasy `DatabaseManager` w pliku `database.py`:

```python
def get_ads_by_custom_filter(self, **filters):
    """Własne zapytanie."""
    with self.get_cursor(commit=False) as cursor:
        cursor.execute("""
            SELECT * FROM ads
            WHERE ...
        """, (params,))
        return cursor.fetchall()
```

### Dodawanie indeksów

Jeśli zauważysz wolne zapytania, dodaj indeksy w `schema.sql`:

```sql
CREATE INDEX idx_custom ON ads(column1, column2);
```

## Maintenance

### Aktualizacja danych

```sql
-- Usuń stare nieaktywne ogłoszenia (starsze niż 90 dni)
DELETE FROM ads
WHERE status != 'active'
    AND modified_at < NOW() - INTERVAL '90 days';

-- Vacuum i analyze dla lepszej wydajności
VACUUM ANALYZE ads;
```

### Backup

```bash
# Backup bazy
pg_dump -U otodom_user otodom_db > backup.sql

# Restore
psql -U otodom_user -d otodom_db < backup.sql
```

## Troubleshooting

### Problem: Brak rozszerzenia postgis

```sql
-- W psql jako superuser:
CREATE EXTENSION postgis;
CREATE EXTENSION pg_trgm;
```

### Problem: Wolne zapytania

```sql
-- Sprawdź czy indeksy są używane
EXPLAIN ANALYZE SELECT ...;

-- Przebuduj indeksy
REINDEX DATABASE otodom_db;
```

### Problem: Błędy połączenia

- Sprawdź czy PostgreSQL jest uruchomiony: `sudo systemctl status postgresql`
- Sprawdź connection string w `.env`
- Sprawdź `pg_hba.conf` dla uprawnień użytkownika

## TODO / Przyszłe rozszerzenia

- [ ] Scraping wielu stron (paginacja)
- [ ] Scheduled scraping (cron/celery)
- [ ] REST API dla wyszukiwarki
- [ ] Frontend (React/Vue)
- [ ] Powiadomienia o nowych ofertach
- [ ] Machine learning (predykcja cen)
- [ ] Export do CSV/Excel
- [ ] Graficzne mapy cieplne

## Licencja

Projekt edukacyjny. Szanuj regulamin Otodom.pl i nie nadużywaj scrapingu.

## Autor

Projekt stworzony dla potrzeb analizy rynku nieruchomości.
