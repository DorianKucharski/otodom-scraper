from __future__ import annotations

SCRAPER_SERVICE = "scraper"
ENRICHER_SERVICE = "enricher"

SERVICE_LABELS: dict[str, str] = {
    SCRAPER_SERVICE: "Scraper",
    ENRICHER_SERVICE: "Enricher",
}

STALE_AFTER_SECONDS = 180
