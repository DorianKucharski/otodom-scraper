import os
from dotenv import load_dotenv
from sqlalchemy import select, func, and_, or_

from database import DatabaseManager
from models import (
    Ad, City, District, AdFeature, AdFlatEquipment,
    AdFlatArea, AdBuildingConvenience
)

load_dotenv()

db = DatabaseManager(os.getenv('DATABASE_URL'))


def example_basic_queries():
    print("\n" + "="*80)
    print("PODSTAWOWE ZAPYTANIA ORM")
    print("="*80 + "\n")

    with db.get_session() as session:
        ad = session.get(Ad, 67537414)
        if ad:
            print(f"1. Ogłoszenie: {ad.title}")
            print(f"   Cena: {ad.price_value:,} PLN")
            print(f"   Miasto: {ad.city.name if ad.city else 'N/A'}")
            print(f"   Liczba zdjęć: {len(ad.images)}")
            print(f"   Liczba cech: {len(ad.features)}")

        print("\n2. Mieszkania 2-pokojowe w Lublinie (top 5):")
        ads = (
            session.query(Ad)
            .join(City)
            .filter(
                City.name == 'Lublin',
                Ad.flat_number_of_rooms == 2,
                Ad.status == 'active'
            )
            .order_by(Ad.price_value)
            .limit(5)
            .all()
        )

        for ad in ads:
            print(f"   - {ad.title[:50]}... | {ad.price_value:,} PLN | {ad.area_value}m²")

        print("\n3. Statystyki mieszkań 2-pokojowych w Lublinie:")
        stats = (
            session.query(
                func.count(Ad.id).label('count'),
                func.avg(Ad.price_value).label('avg_price'),
                func.min(Ad.price_value).label('min_price'),
                func.max(Ad.price_value).label('max_price')
            )
            .join(City)
            .filter(
                City.name == 'Lublin',
                Ad.flat_number_of_rooms == 2,
                Ad.status == 'active'
            )
            .first()
        )

        print(f"   Liczba ofert: {stats.count}")
        print(f"   Średnia cena: {stats.avg_price:,.0f} PLN")
        print(f"   Zakres: {stats.min_price:,} - {stats.max_price:,} PLN")


def example_relationships():
    print("\n" + "="*80)
    print("RELACJE W ORM")
    print("="*80 + "\n")

    with db.get_session() as session:
        ad = session.query(Ad).filter(Ad.status == 'active').first()

        if ad:
            print(f"Ogłoszenie: {ad.title[:60]}...")

            print(f"\nCechy ({len(ad.features)}):")
            for feature in ad.features[:5]:
                print(f"  - {feature.feature}")

            print(f"\nWyposażenie ({len(ad.flat_equipment)}):")
            for eq in ad.flat_equipment[:5]:
                print(f"  - {eq.equipment}")

            print(f"\nLokalizacja:")
            if ad.city:
                print(f"  Miasto: {ad.city.name}")
            if ad.district:
                print(f"  Dzielnica: {ad.district.name}")
            if ad.province:
                print(f"  Województwo: {ad.province.name}")

            if ad.owner:
                print(f"\nWłaściciel: {ad.owner.name} ({ad.owner.type})")
                print(f"  Telefony: {', '.join([p.phone for p in ad.owner.phones])}")


def example_advanced_filtering():
    print("\n" + "="*80)
    print("ZAAWANSOWANE FILTROWANIE")
    print("="*80 + "\n")

    with db.get_session() as session:
        print("1. Mieszkania z windą i balkonem:")

        has_lift = (
            select(AdBuildingConvenience.ad_id)
            .where(AdBuildingConvenience.convenience.like('%LIFT%'))
        )

        has_balcony = (
            select(AdFlatArea.ad_id)
            .where(AdFlatArea.area.like('%balcon%'))
        )

        ads = (
            session.query(Ad)
            .filter(
                Ad.id.in_(has_lift),
                Ad.id.in_(has_balcony),
                Ad.status == 'active'
            )
            .limit(5)
            .all()
        )

        for ad in ads:
            print(f"   - {ad.title[:50]}... | {ad.price_value:,} PLN")

        print("\n2. Mieszkania z minimum 5 udogodnieniami:")

        ads_with_features = (
            session.query(
                Ad,
                func.count(AdFeature.id).label('feature_count')
            )
            .outerjoin(AdFeature)
            .filter(Ad.status == 'active')
            .group_by(Ad.id)
            .having(func.count(AdFeature.id) >= 5)
            .order_by(func.count(AdFeature.id).desc())
            .limit(5)
            .all()
        )

        for ad, count in ads_with_features:
            print(f"   - {ad.title[:50]}... | Cechy: {count} | {ad.price_value:,} PLN")

        print("\n3. Mieszkania w przedziale cenowym 400-500k PLN:")

        ads = (
            session.query(Ad)
            .filter(
                Ad.price_value.between(400000, 500000),
                Ad.status == 'active',
                Ad.city_id == '190'
            )
            .order_by(Ad.price_per_m2)
            .limit(5)
            .all()
        )

        for ad in ads:
            print(f"   - {ad.title[:50]}... | {ad.price_value:,} PLN ({ad.price_per_m2:,} PLN/m²)")


def example_complex_queries():
    print("\n" + "="*80)
    print("ZŁOŻONE ZAPYTANIA ANALITYCZNE")
    print("="*80 + "\n")

    with db.get_session() as session:
        print("1. Top 5 dzielnic po średniej cenie (Lublin):")

        results = (
            session.query(
                District.name,
                func.count(Ad.id).label('ad_count'),
                func.avg(Ad.price_value).label('avg_price'),
                func.avg(Ad.price_per_m2).label('avg_price_m2')
            )
            .join(Ad)
            .join(City)
            .filter(
                City.name == 'Lublin',
                Ad.status == 'active'
            )
            .group_by(District.id, District.name)
            .having(func.count(Ad.id) >= 3)
            .order_by(func.avg(Ad.price_per_m2).desc())
            .limit(5)
            .all()
        )

        for district, count, avg_price, avg_m2 in results:
            print(f"   {district}: {count} ofert | Śr. cena: {avg_price:,.0f} PLN | Śr. cena/m²: {avg_m2:,.0f} PLN")

        print("\n2. Rozkład liczby pokoi:")

        results = (
            session.query(
                Ad.flat_number_of_rooms,
                func.count(Ad.id).label('count'),
                func.avg(Ad.price_value).label('avg_price')
            )
            .filter(
                Ad.status == 'active',
                Ad.city_id == '190',
                Ad.flat_number_of_rooms.isnot(None)
            )
            .group_by(Ad.flat_number_of_rooms)
            .order_by(Ad.flat_number_of_rooms)
            .all()
        )

        for rooms, count, avg_price in results:
            print(f"   {rooms} pokoi: {count} ofert | Śr. cena: {avg_price:,.0f} PLN")

        # 3. Top cechy (najpopularniejsze)
        print("\n3. Top 10 najpopularniejszych cech:")

        results = (
            session.query(
                AdFeature.feature,
                func.count(AdFeature.id).label('count')
            )
            .join(Ad)
            .filter(Ad.status == 'active')
            .group_by(AdFeature.feature)
            .order_by(func.count(AdFeature.id).desc())
            .limit(10)
            .all()
        )

        for feature, count in results:
            print(f"   {feature}: {count} ogłoszeń")


def example_orm_expressions():
    """Przykłady wyrażeń ORM (and_, or_, not_)"""
    print("\n" + "="*80)
    print("WYRAŻENIA LOGICZNE W ORM")
    print("="*80 + "\n")

    with db.get_session() as session:
        # 1. OR - mieszkania 2 lub 3 pokojowe
        print("1. Mieszkania 2 LUB 3 pokojowe w Lublinie:")

        ads = (
            session.query(Ad)
            .filter(
                Ad.city_id == '190',
                or_(
                    Ad.flat_number_of_rooms == 2,
                    Ad.flat_number_of_rooms == 3
                ),
                Ad.status == 'active'
            )
            .limit(5)
            .all()
        )

        for ad in ads:
            print(f"   - {ad.flat_number_of_rooms} pokoi | {ad.price_value:,} PLN | {ad.title[:40]}...")

        # 2. AND + OR - kombinacje
        print("\n2. Mieszkania (2-3 pokoje) I (300-500k PLN):")

        ads = (
            session.query(Ad)
            .filter(
                and_(
                    or_(
                        Ad.flat_number_of_rooms == 2,
                        Ad.flat_number_of_rooms == 3
                    ),
                    Ad.price_value.between(300000, 500000),
                    Ad.status == 'active',
                    Ad.city_id == '190'
                )
            )
            .order_by(Ad.price_per_m2)
            .limit(5)
            .all()
        )

        for ad in ads:
            print(f"   - {ad.flat_number_of_rooms} pokoi | {ad.price_value:,} PLN | {ad.price_per_m2:,} PLN/m²")


def example_raw_sql():
    """Przykład użycia raw SQL gdy potrzebne"""
    print("\n" + "="*80)
    print("RAW SQL (gdy potrzebne)")
    print("="*80 + "\n")

    with db.get_session() as session:
        # Możesz używać raw SQL gdy ORM nie wystarcza
        from sqlalchemy import text

        result = session.execute(text("""
            SELECT
                c.name as city,
                COUNT(*) as ads,
                AVG(a.price_value)::int as avg_price
            FROM ads a
            JOIN cities c ON a.city_id = c.id
            WHERE a.status = 'active'
            GROUP BY c.name
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """))

        print("Top 5 miast po liczbie ogłoszeń:")
        for row in result:
            print(f"   {row.city}: {row.ads} ofert | Śr. cena: {row.avg_price:,} PLN")


if __name__ == '__main__':
    """Uruchom wszystkie przykłady"""
    try:
        example_basic_queries()
        example_relationships()
        example_advanced_filtering()
        example_complex_queries()
        example_orm_expressions()
        example_raw_sql()

        print("\n" + "="*80)
        print("KONIEC PRZYKŁADÓW")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\nBłąd: {e}")
        print("\nUpewnij się że:")
        print("1. Baza danych jest uruchomiona")
        print("2. DATABASE_URL w .env jest prawidłowy")
        print("3. Tabele zostały utworzone (db_manager.create_all_tables())")
        print("4. Jest przynajmniej jedno ogłoszenie w bazie")
