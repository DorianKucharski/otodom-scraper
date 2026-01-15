# Instalacja - Otodom Scraper

## Wymagania

- Python 3.10 lub nowszy
- PostgreSQL 17 (lub 13+)
- pip

## Krok po kroku

### 1. Sklonuj repozytorium
```bash
cd otodom-scrapper
```

### 2. Utwórz wirtualne środowisko (opcjonalne, ale zalecane)
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 3. Zainstaluj zależności Python
```bash
pip install -r requirements.txt
```

### 4. Zainstaluj PostgreSQL i rozszerzenia

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql-17 postgresql-17-postgis-3
```

**macOS (Homebrew):**
```bash
brew install postgresql@17 postgis
brew services start postgresql@17
```

**Windows:**
- Pobierz installer z [postgresql.org](https://www.postgresql.org/download/windows/)
- Podczas instalacji zaznacz PostGIS w Stack Builder

### 5. Utwórz bazę danych

```bash
# Zaloguj się do PostgreSQL
psql -U postgres

# W konsoli PostgreSQL:
CREATE DATABASE otodom_db;
CREATE USER otodom_user WITH PASSWORD 'twoje_haslo';
GRANT ALL PRIVILEGES ON DATABASE otodom_db TO otodom_user;

# W PostgreSQL 15+, dodatkowo:
\c otodom_db
GRANT ALL ON SCHEMA public TO otodom_user;

# Wyjdź
\q
```

### 6. Skonfiguruj connection string

```bash
# Skopiuj przykładową konfigurację
cp .env.example .env
```

Edytuj plik `.env`:
```bash
DATABASE_URL=postgresql://otodom_user:twoje_haslo@localhost:5432/otodom_db
```

### 7. Utwórz tabele przez migracje Alembic

**Opcja A: Automatyczna migracja (zalecane)**
```bash
# Wygeneruj początkową migrację
alembic revision --autogenerate -m "Initial migration"

# Zastosuj migrację
alembic upgrade head
```

**Opcja B: Bezpośrednie utworzenie tabel**

Odkomentuj w `main.py`:
```python
db_manager.create_all_tables()
```

Uruchom:
```bash
python main.py
```

### 8. Weryfikacja instalacji

```bash
# Test połączenia
python -c "from database import DatabaseManager; import os; from dotenv import load_dotenv; load_dotenv(); db = DatabaseManager(os.getenv('DATABASE_URL')); print('OK!')"
```

Jeśli wyświetli się "OK!" - instalacja zakończona sukcesem!

### 9. Uruchom przykładową aplikację

```bash
python main.py
```

## Troubleshooting

### Problem: "No module named 'psycopg2'"
```bash
pip install psycopg2-binary
```

### Problem: "Extension postgis does not exist"
```bash
# Zaloguj się jako superuser postgres
psql -U postgres -d otodom_db

# W konsoli PostgreSQL:
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\q
```

### Problem: "FATAL: password authentication failed"
Sprawdź:
1. Czy hasło w `.env` jest poprawne
2. Czy użytkownik `otodom_user` istnieje
3. Plik `pg_hba.conf` (zazwyczaj w `/etc/postgresql/17/main/pg_hba.conf`)

### Problem: "FATAL: database otodom_db does not exist"
```bash
psql -U postgres -c "CREATE DATABASE otodom_db;"
```

### Problem: "Connection refused"
Sprawdź czy PostgreSQL działa:
```bash
# Linux
sudo systemctl status postgresql
sudo systemctl start postgresql

# macOS
brew services list
brew services start postgresql@17

# Windows
# Services → PostgreSQL → Start
```

### Problem: Import error "cannot import name DatabaseManager"
Upewnij się że jesteś w głównym katalogu projektu:
```bash
cd otodom-scrapper
python main.py
```

## Opcjonalne: Development setup

### Pre-commit hooks (formatowanie kodu)
```bash
pip install pre-commit black ruff
pre-commit install
```

### Jupyter dla eksperymentów
```bash
pip install jupyter
jupyter notebook
```

### pgAdmin (GUI dla PostgreSQL)
- Pobierz z [pgadmin.org](https://www.pgadmin.org/download/)

## Następne kroki

Po instalacji zobacz:
- `QUICKSTART.md` - szybki start
- `README.md` - pełna dokumentacja
- `examples.py` - przykłady zapytań

## Pomoc

Jeśli coś nie działa:
1. Sprawdź czy wszystkie requirements są zainstalowane: `pip list`
2. Sprawdź logi PostgreSQL: `sudo journalctl -u postgresql`
3. Sprawdź czy extensions są zainstalowane: `psql -U postgres -d otodom_db -c "\dx"`
4. Zobacz szczegóły błędu w logach Python
