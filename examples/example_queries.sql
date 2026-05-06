-- ============================================================================
-- PRZYKŁADOWE ZAPYTANIA SQL
-- Otodom Scraper Database - Advanced Search Examples
-- ============================================================================

-- ============================================================================
-- 1. PODSTAWOWE ZAPYTANIA
-- ============================================================================

-- Ogłoszenia w danym mieście
SELECT ads.id, title, price_value, price_per_m2, area_value, flat_number_of_rooms
FROM ads
JOIN cities on ads.city_id = cities.id
WHERE cities.name = 'Lublin'
    AND status = 'active'
ORDER BY created_at DESC
LIMIT 20;

-- Najtańsze mieszkania
SELECT title, price_value, price_per_m2, city_name, district_name
FROM vw_ads_detailed
WHERE status = 'active'
    AND property_type = 'FLAT'
ORDER BY price_value ASC
LIMIT 10;

-- ============================================================================
-- 2. SORTOWANIE PO LICZBIE CECH
-- ============================================================================
SELECT a.id,
       a.url,
       a.title,
       a.price_value,
       a.price_per_m2,
       a.area_value,
       COUNT(DISTINCT af.feature)     as features_count,
       COUNT(DISTINCT ae.equipment)   as equipment_count,
       COUNT(DISTINCT aa.area)        as extra_areas_count,
       COUNT(DISTINCT ac.convenience) as conveniences_count
FROM ads a
         LEFT JOIN cities c on a.city_id = c.id
         LEFT JOIN ad_features af ON a.id = af.ad_id
         LEFT JOIN ad_flat_equipment ae ON a.id = ae.ad_id
         LEFT JOIN ad_flat_areas aa ON a.id = aa.ad_id
         LEFT JOIN ad_building_conveniences ac ON a.id = ac.ad_id
WHERE 1 = 1
  AND a.status = 'active'
  AND c.name = 'Kraków'
  AND a.modified_at >= '2026-04-01'
  AND a.price_value <= 1500000
  AND a.price_value >= 800000
  AND (
    1 = 1
        or a.market = 'SECONDARY'
        or a.market = 'PRIMARY'
        or a.market = ''
    )
  AND (
    1 = 1
        or a.advertiser_type = 'private'
        or a.advertiser_type= 'business'
    )
  AND (
    1 = 1
        or a.property_condition = 'READY_TO_USE'
        or a.property_condition = 'TO_COMPLETION'
        or a.property_condition = 'TO_RENOVATION'
        or a.property_condition is null
    )
GROUP BY a.id
ORDER BY features_count DESC,
         equipment_count DESC,
         conveniences_count DESC,
         extra_areas_count DESC,

-- Mieszkania z największą liczbą cech i udogodnień
SELECT
    a.id,
    a.title,
    a.price_value,
    a.price_per_m2,
    a.area_value,
    COUNT(DISTINCT af.feature) as features_count,
    COUNT(DISTINCT ae.equipment) as equipment_count,
    COUNT(DISTINCT aa.area) as extra_areas_count,
    COUNT(DISTINCT ac.convenience) as conveniences_count
FROM ads a
LEFT JOIN ad_features af ON a.id = af.ad_id
LEFT JOIN ad_flat_equipment ae ON a.id = ae.ad_id
LEFT JOIN ad_flat_areas aa ON a.id = aa.ad_id
LEFT JOIN ad_building_conveniences ac ON a.id = ac.ad_id
WHERE a.status = 'active'
    AND a.city_id = '190'  -- Lublin
GROUP BY a.id
ORDER BY
    features_count DESC,
    equipment_count DESC,
    conveniences_count DESC,
    extra_areas_count DESC
LIMIT 20;

-- Ogłoszenia z minimum 10 cechami
SELECT
    a.title,
    a.price_value,
    COUNT(DISTINCT f.feature) as feature_count,
    ARRAY_AGG(DISTINCT f.feature) as features
FROM ads a
JOIN ad_features f ON a.id = f.ad_id
WHERE a.status = 'active'
GROUP BY a.id, a.title, a.price_value
HAVING COUNT(DISTINCT f.feature) >= 10
ORDER BY feature_count DESC;

-- ============================================================================
-- 3. FILTROWANIE PO KONKRETNYCH CECHACH
-- ============================================================================

-- Mieszkania z windą
SELECT DISTINCT a.id, a.title, a.price_value, a.building_number_of_floors
FROM ads a
JOIN ad_building_conveniences c ON a.id = c.ad_id
WHERE c.convenience LIKE '%LIFT%'
    AND a.status = 'active'
ORDER BY a.price_value;

-- Mieszkania z balkonem i parkingiem
SELECT DISTINCT a.id, a.title, a.price_value, a.area_value
FROM ads a
WHERE a.status = 'active'
    AND EXISTS (
        SELECT 1 FROM ad_flat_areas aa
        WHERE aa.ad_id = a.id AND aa.area LIKE '%balcon%'
    )
    AND EXISTS (
        SELECT 1 FROM ad_flat_areas aa2
        WHERE aa2.ad_id = a.id AND aa2.area LIKE '%garage%'
    )
ORDER BY a.price_value;

-- Mieszkania ze wszystkimi wybranymi cechami
WITH required_features AS (
    SELECT unnest(ARRAY['internet', 'balkon', 'winda']) as feature
)
SELECT
    a.id,
    a.title,
    a.price_value,
    COUNT(DISTINCT rf.feature) as matched_features
FROM ads a
CROSS JOIN required_features rf
JOIN ad_features af ON a.id = af.ad_id AND af.feature = rf.feature
WHERE a.status = 'active'
GROUP BY a.id, a.title, a.price_value
HAVING COUNT(DISTINCT rf.feature) = (SELECT COUNT(*) FROM required_features)
ORDER BY a.price_value;

-- ============================================================================
-- 4. ZAPYTANIA GEOGRAFICZNE (LOKALIZACJA)
-- ============================================================================

-- Ogłoszenia w promieniu 1km od punktu (centrum Lublina)
SELECT * FROM get_ads_within_radius(51.2465, 22.5684, 1000)
LIMIT 20;

-- Zagęszczenie ofert w okolicy
SELECT * FROM get_ad_density_in_area(51.2465, 22.5684, 2000);

-- Wszystkie ogłoszenia w promieniu z dodatkowymi informacjami
SELECT
    a.id,
    a.title,
    a.price_value,
    a.price_per_m2,
    ST_Distance(
        a.location_point::geography,
        ST_SetSRID(ST_MakePoint(22.5684, 51.2465), 4326)::geography
    ) as distance_meters
FROM ads a
WHERE a.location_point IS NOT NULL
    AND a.status = 'active'
    AND ST_DWithin(
        a.location_point::geography,
        ST_SetSRID(ST_MakePoint(22.5684, 51.2465), 4326)::geography,
        1000
    )
ORDER BY distance_meters;

-- Mapa cieplna cen (grid 0.01° = ok. 1km)
SELECT
    ROUND(latitude, 2) as lat_grid,
    ROUND(longitude, 2) as lon_grid,
    COUNT(*) as ad_count,
    ROUND(AVG(price_value)::numeric, 0) as avg_price,
    ROUND(AVG(price_per_m2)::numeric, 0) as avg_price_per_m2,
    MIN(price_value) as min_price,
    MAX(price_value) as max_price
FROM ads
WHERE status = 'active'
    AND city_id = '190'
    AND latitude IS NOT NULL
    AND longitude IS NOT NULL
GROUP BY lat_grid, lon_grid
HAVING COUNT(*) >= 3
ORDER BY avg_price DESC;

-- ============================================================================
-- 5. STATYSTYKI I AGREGACJE
-- ============================================================================

-- Statystyki per miasto
SELECT * FROM vw_ads_by_city
ORDER BY ad_count DESC;

-- Statystyki per dzielnica
SELECT
    city_name,
    district_name,
    ad_count,
    ROUND(avg_price::numeric, 0) as avg_price,
    ROUND(avg_price_per_m2::numeric, 0) as avg_price_per_m2
FROM vw_ads_by_district
WHERE city_name = 'Lublin'
ORDER BY avg_price_per_m2 DESC;

-- Rozkład cen (histogram)
SELECT
    CASE
        WHEN price_value < 200000 THEN '< 200k'
        WHEN price_value < 300000 THEN '200-300k'
        WHEN price_value < 400000 THEN '300-400k'
        WHEN price_value < 500000 THEN '400-500k'
        WHEN price_value < 700000 THEN '500-700k'
        ELSE '> 700k'
    END as price_range,
    COUNT(*) as count,
    ROUND(AVG(area_value)::numeric, 1) as avg_area
FROM ads
WHERE status = 'active'
    AND city_id = '190'
GROUP BY price_range
ORDER BY MIN(price_value);

-- Średnia cena per liczba pokoi
SELECT
    flat_number_of_rooms as rooms,
    COUNT(*) as ad_count,
    ROUND(AVG(price_value)::numeric, 0) as avg_price,
    ROUND(AVG(price_per_m2)::numeric, 0) as avg_price_per_m2,
    ROUND(AVG(area_value)::numeric, 1) as avg_area
FROM ads
WHERE status = 'active'
    AND city_id = '190'
    AND flat_number_of_rooms IS NOT NULL
GROUP BY flat_number_of_rooms
ORDER BY flat_number_of_rooms;

-- Top 10 najpopularniejszych cech
SELECT
    feature,
    COUNT(*) as count
FROM ad_features
JOIN ads ON ad_features.ad_id = ads.id
WHERE ads.status = 'active'
GROUP BY feature
ORDER BY count DESC
LIMIT 10;

-- ============================================================================
-- 6. ZAAWANSOWANE FILTRY I WYSZUKIWANIE
-- ============================================================================

-- Kompleksowe wyszukiwanie z wieloma filtrami
SELECT
    a.id,
    a.title,
    a.price_value,
    a.price_per_m2,
    a.area_value,
    a.flat_number_of_rooms,
    c.name as city_name,
    d.name as district_name,
    COUNT(DISTINCT af.feature) as features_count
FROM ads a
LEFT JOIN cities c ON a.city_id = c.id
LEFT JOIN districts d ON a.district_id = d.id
LEFT JOIN ad_features af ON a.id = af.ad_id
WHERE
    a.status = 'active'
    AND a.property_type = 'FLAT'
    AND a.city_id = '190'  -- Lublin
    AND a.flat_number_of_rooms >= 2
    AND a.price_value BETWEEN 300000 AND 500000
    AND a.area_value BETWEEN 40 AND 60
    AND a.building_year >= 2000
    -- Dodatkowe filtry:
    AND a.building_heating = 'URBAN'
    AND a.property_ownership = 'FULL_OWNERSHIP'
GROUP BY a.id, c.name, d.name
HAVING COUNT(DISTINCT af.feature) >= 5
ORDER BY
    a.price_per_m2 ASC,
    features_count DESC
LIMIT 20;

-- Wyszukiwanie pełnotekstowe w tytule i opisie
SELECT
    id,
    title,
    price_value,
    SIMILARITY(title, 'słoneczne centrum') as title_similarity
FROM ads
WHERE
    status = 'active'
    AND (
        title ILIKE '%słoneczne%'
        OR description ILIKE '%słoneczne%'
    )
ORDER BY title_similarity DESC
LIMIT 10;

-- Ogłoszenia "best value" (najlepsza wartość za cenę)
WITH feature_stats AS (
    SELECT
        ad_id,
        COUNT(DISTINCT feature) as feature_count
    FROM ad_features
    GROUP BY ad_id
)
SELECT
    a.id,
    a.title,
    a.price_value,
    a.price_per_m2,
    a.area_value,
    COALESCE(fs.feature_count, 0) as features,
    -- Score: więcej cech + niższa cena/m² = lepszy score
    (COALESCE(fs.feature_count, 0) * 1000.0 / NULLIF(a.price_per_m2, 0)) as value_score
FROM ads a
LEFT JOIN feature_stats fs ON a.id = fs.ad_id
WHERE
    a.status = 'active'
    AND a.city_id = '190'
    AND a.price_per_m2 > 0
ORDER BY value_score DESC
LIMIT 20;

-- ============================================================================
-- 7. PORÓWNANIA I TRENDY
-- ============================================================================

-- Porównanie cen między dzielnicami
SELECT
    d.name as district,
    COUNT(*) as ads,
    ROUND(AVG(a.price_per_m2)::numeric, 0) as avg_price_m2,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.price_per_m2) as median_price_m2,
    MIN(a.price_per_m2) as min_price_m2,
    MAX(a.price_per_m2) as max_price_m2
FROM ads a
JOIN districts d ON a.district_id = d.id
WHERE a.status = 'active'
    AND a.city_id = '190'
    AND a.price_per_m2 > 0
GROUP BY d.name
HAVING COUNT(*) >= 5
ORDER BY avg_price_m2 DESC;

-- Najnowsze ogłoszenia (ostatnie 7 dni)
SELECT
    id,
    title,
    price_value,
    price_per_m2,
    created_at,
    NOW() - created_at as age
FROM ads
WHERE
    status = 'active'
    AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 20;

-- Zmiana cen (modyfikowane ogłoszenia)
SELECT
    id,
    title,
    price_value,
    created_at,
    modified_at,
    modified_at - created_at as time_on_market
FROM ads
WHERE
    status = 'active'
    AND modified_at > created_at
    AND modified_at >= NOW() - INTERVAL '7 days'
ORDER BY modified_at DESC;

-- ============================================================================
-- 8. RAPORTY DLA UŻYTKOWNIKA
-- ============================================================================

-- Raport: "Podobne mieszkania do wybranego"
-- (zastąp wartości parametrami z wybranego mieszkania)
WITH target_ad AS (
    SELECT
        price_value,
        area_value,
        flat_number_of_rooms,
        city_id,
        district_id
    FROM ads
    WHERE id = 67537414  -- ID wybranego ogłoszenia
)
SELECT
    a.id,
    a.title,
    a.price_value,
    a.price_per_m2,
    a.area_value,
    ABS(a.price_value - t.price_value) as price_diff,
    ABS(a.area_value - t.area_value) as area_diff
FROM ads a
CROSS JOIN target_ad t
WHERE
    a.status = 'active'
    AND a.id != 67537414
    AND a.flat_number_of_rooms = t.flat_number_of_rooms
    AND a.city_id = t.city_id
    AND ABS(a.price_value - t.price_value) < 100000
    AND ABS(a.area_value - t.area_value) < 15
ORDER BY
    ABS(a.price_value - t.price_value) +
    ABS(a.area_value - t.area_value) * 1000
LIMIT 10;

-- Raport: "Najlepsze oferty w budżecie"
-- Mieszkania z dużą liczbą cech w danym budżecie
SELECT
    a.id,
    a.title,
    a.price_value,
    a.area_value,
    a.flat_number_of_rooms,
    COUNT(DISTINCT af.feature) +
    COUNT(DISTINCT ae.equipment) as total_features
FROM ads a
LEFT JOIN ad_features af ON a.id = af.ad_id
LEFT JOIN ad_flat_equipment ae ON a.id = ae.ad_id
WHERE
    a.status = 'active'
    AND a.price_value BETWEEN 400000 AND 450000  -- Twój budżet
    AND a.city_id = '190'
GROUP BY a.id
ORDER BY total_features DESC, a.price_value ASC
LIMIT 10;

-- ============================================================================
-- 9. MAINTENANCE QUERIES
-- ============================================================================

-- Statystyki tabeli
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_live_tup as rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Najbardziej aktywne dzielnice (najwięcej ogłoszeń)
SELECT
    d.name,
    COUNT(*) as ads
FROM ads a
JOIN districts d ON a.district_id = d.id
WHERE a.status = 'active'
GROUP BY d.name
ORDER BY ads DESC
LIMIT 10;

-- Sprawdzenie indeksów
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
