from __future__ import annotations

from typing import Optional

from .models import AdMarketSignals

LISTING_HISTORY_MIN_DAYS = 45


def listing_history_phrase(signals: Optional[AdMarketSignals], current_price: Optional[int]) -> Optional[str]:
    if signals is None or (signals.listings_count < 2 and signals.days_on_market < LISTING_HISTORY_MIN_DAYS):
        return None
    parts = [f"ten sam lokal ogłaszany od {signals.first_listed_at:%Y-%m-%d}, {signals.days_on_market} dni na rynku"]
    if signals.listings_count > 1:
        parts.append(f"{signals.listings_count} ogłoszeń od {signals.advertisers_count} ogłoszeniodawców")
    if signals.first_price and signals.first_price != current_price:
        parts.append(f"pierwsza znana cena {_money(signals.first_price)}")
    return ", ".join(parts)


def comparables_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.comparables_median_price_per_m2:
        return None
    phrase = (
        f"wśród {signals.comparables_count} podobnych ofert (metraż ±35%) do {signals.comparables_radius_m} m "
        f"od pinezki mediana to {signals.comparables_median_price_per_m2} zł za metr"
    )
    if signals.price_vs_comparables_pct is not None:
        difference = float(signals.price_vs_comparables_pct)
        relation = "powyżej" if difference > 0 else "poniżej"
        phrase += f", ta oferta jest {abs(difference):.0f}% {relation}"
    return phrase


def transactions_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.transactions_median_price_per_m2:
        return None
    phrase = (
        f"mediana {signals.transactions_count} prawdziwych transakcji z ostatnich 2 lat (RCN, metraż ±35%, do "
        f"{signals.transactions_radius_m} m) to {signals.transactions_median_price_per_m2} zł za metr"
    )
    if signals.price_vs_transactions_pct is not None:
        difference = float(signals.price_vs_transactions_pct)
        relation = "powyżej" if difference > 0 else "poniżej"
        phrase += f", ta oferta jest {abs(difference):.0f}% {relation}"
    return phrase


def area_warnings_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.area_notes:
        return None
    return " ".join(signals.area_notes)


def location_warnings_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.location_notes:
        return None
    return " ".join(signals.location_notes)


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " zł"
