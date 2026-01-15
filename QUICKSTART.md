# Quick Start - Otodom Scraper

Szybki start dla nowych użytkowników.

## 5-minutowy start

### 1. Sklonuj i zainstaluj (2 min)

```bash
cd otodom-scrapper
pip install -r requirements.txt
```

### 2. Skonfiguruj bazę danych (2 min)

```bash
# Utwórz bazę PostgreSQL
psql -U postgres -c "CREATE DATABASE otodom_db;"
psql -U postgres -c "CREATE USER otodom_user WITH PASSWORD 'haslo123';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE otodom_db TO otodom_user;"
```

```bash
# Utwórz plik .env
cp .env.example .env
```

Edytuj `.env`:
```
DATABASE_URL=postgresql://otodom_user:haslo123@localhost:5432/otodom_db
```

### 3. Inicjalizuj schemat (30 sek)

```bash
# Wygeneruj i zastosuj migracje
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 4. Uruchom scraper (30 sek)

```bash
python main.py
```

Gotowe! 🎉

## Podstawowe użycie

### Scraping jednego ogłoszenia

```python
from scraper import Scraper
from parser import OtodomParser
from database import DatabaseManager
import os

db = DatabaseManager(os.getenv('DATABASE_URL'))
scraper = Scraper()
parser = OtodomParser()

url = "https://www.otodom.pl/pl/oferta/..."
data = scraper.scrape(url)
ad = parser.parse(data)
db.save_ad(ad)
print(f"Zapisano: {ad.title}")
```

### Proste zapytanie

```python
from models import Ad, City

with db.get_session() as session:
    # Mieszkania 2-pokojowe w Lublinie
    ads = session.query(Ad).join(City).filter(
        City.name == 'Lublin',
        Ad.flat_number_of_rooms == 2,
        Ad.status == 'active'
    ).limit(10).all()

    for ad in ads:
        print(f"{ad.title}: {ad.price_value:,} PLN")
```

### Dostęp do relacji

```python
with db.get_session() as session:
    ad = session.get(Ad, 67537414)

    # Dostęp do powiązanych obiektów
    print(f"Miasto: {ad.city.name}")
    print(f"Dzielnica: {ad.district.name}")
    print(f"Właściciel: {ad.owner.name}")
    print(f"Cechy: {[f.feature for f in ad.features]}")
```

## Zaawansowane zapytania

### Sortowanie po liczbie cech

```python
ads = db.get_ads_sorted_by_feature_count(
    city_id='190',  # Lublin
    min_features=5,
    limit=20
)

for ad in ads:
    print(f"{ad['title']}: {ad['features_count']} cech")
```

### Wyszukiwanie geograficzne

```python
# Oferty w promieniu 1km od centrum
ads = db.get_ads_within_radius(
    latitude=51.2465,
    longitude=22.5684,
    radius_meters=1000
)

for ad in ads:
    print(f"{ad['title']}: {ad['distance_meters']:.0f}m")
```

### Zagęszczenie ofert

```python
density = db.get_ad_density_stats(
    latitude=51.2465,
    longitude=22.5684,
    radius_meters=2000
)

print(f"Ofert w okolicy: {density['ad_count']}")
print(f"Zagęszczenie: {density['density_per_km2']:.2f} ofert/km²")
print(f"Średnia cena: {density['avg_price']:,} PLN")
```

## Więcej przykładów

Zobacz:
- `examples.py` - kompletne przykłady zapytań ORM
- `example_queries.sql` - przykłady SQL
- `README.md` - pełna dokumentacja

## Najczęstsze komendy

```bash
# Migracje
alembic revision --autogenerate -m "opis zmian"  # Nowa migracja
alembic upgrade head                              # Zastosuj migracje
alembic downgrade -1                              # Cofnij ostatnią
alembic history                                   # Historia
alembic current                                   # Aktualna wersja

# Backup
pg_dump -U otodom_user otodom_db > backup.sql
psql -U otodom_user -d otodom_db < backup.sql

# Połączenie do bazy
psql -U otodom_user -d otodom_db
```

## Struktura plików

```
models.py           → Modele SQLAlchemy (definicje tabel)
database.py         → Manager bazy danych (zapytania)
scraper.py          → Scraper Otodom
parser.py           → Parser HTML → Python dataclasses
main.py             → Główna aplikacja
examples.py         → Przykłady użycia ORM
alembic/            → Migracje bazy danych
```

## Tips & Tricks

### 1. Eager loading (szybsze zapytania z relacjami)

```python
from sqlalchemy.orm import joinedload

ads = session.query(Ad).options(
    joinedload(Ad.city),
    joinedload(Ad.features)
).all()

# Teraz ad.city nie wykonuje dodatkowego query
```

### 2. Batch insert (wiele ogłoszeń naraz)

```python
ads = []  # lista Ad dataclass
for ad_data in ads:
    db.save_ad(ad_data)  # Każde w transakcji
```

### 3. Raw SQL gdy ORM nie wystarcza

```python
from sqlalchemy import text

with db.get_session() as session:
    result = session.execute(text("""
        SELECT city, COUNT(*) FROM ads GROUP BY city
    """))
    for row in result:
        print(row)
```

### 4. Wyłącz echo SQL (jeśli za dużo logów)

```python
db = DatabaseManager(os.getenv('DATABASE_URL'), echo=False)
```

## Troubleshooting

**Problem: "No module named 'models'"**
```bash
# Upewnij się że jesteś w głównym katalogu projektu
cd otodom-scrapper
python main.py
```

**Problem: "Connection refused"**
```bash
# Sprawdź czy PostgreSQL działa
sudo systemctl status postgresql

# Sprawdź connection string w .env
cat .env
```

**Problem: "Extension postgis does not exist"**
```bash
# Zainstaluj PostGIS
sudo apt-get install postgresql-17-postgis-3  # Ubuntu
brew install postgis  # macOS
```

**Problem: Wolne zapytania**
```sql
-- Sprawdź czy indeksy są używane
EXPLAIN ANALYZE SELECT ...;

-- Przebuduj indeksy
REINDEX DATABASE otodom_db;
```

## Co dalej?

1. ✅ Uruchom `examples.py` żeby zobaczyć więcej przykładów
2. ✅ Przeczytaj `README.md` dla zaawansowanych funkcji
3. ✅ Napisz własne zapytania w `database.py`
4. ✅ Dodaj nowe pola do modeli i wygeneruj migrację
5. ✅ Zbuduj wyszukiwarkę/dashboard na bazie danych

Powodzenia! 🚀
