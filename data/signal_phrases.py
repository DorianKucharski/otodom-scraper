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
    if (signals.active_listings_count or 1) > 1:
        parts.append(f"teraz wystawiony równolegle w {signals.active_listings_count} ogłoszeniach")
    if signals.first_price and signals.first_price != current_price:
        parts.append(f"pierwsza znana cena {_money(signals.first_price)}")
    return ", ".join(parts)


def previous_sale_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.previous_sale_price:
        return None
    return (
        f"prawdopodobnie ten sam lokal sprzedano {signals.previous_sale_at:%Y-%m} za {_money(signals.previous_sale_price)} "
        f"(RCN: ten sam metraż, {signals.previous_sale_distance_m} m od pinezki)"
    )


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


def street_transactions_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.street_transactions_median_price_per_m2:
        return None
    phrase = (
        f"na tej samej ulicy (do 1,5 km, metraż ±35%, mogą to być budynki z innych lat) mediana {signals.street_transactions_count} transakcji "
        f"to {signals.street_transactions_median_price_per_m2} zł za metr"
    )
    if signals.price_vs_street_transactions_pct is not None:
        difference = float(signals.price_vs_street_transactions_pct)
        relation = "powyżej" if difference > 0 else "poniżej"
        phrase += f", ta oferta jest {abs(difference):.0f}% {relation}"
    return phrase


def developer_price_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.developer_price:
        return None
    parts = [
        f"oficjalny cennik dewelopera {signals.developer_name or ''} na dane.gov.pl (lokal {signals.developer_unit}, "
        f"{signals.developer_investment}): {_money(signals.developer_price)}".replace("  ", " ")
    ]
    if signals.developer_price_since:
        parts[0] += f" od {signals.developer_price_since:%Y-%m-%d}"
    if signals.price_vs_developer_pct is not None and abs(float(signals.price_vs_developer_pct)) >= 1:
        difference = float(signals.price_vs_developer_pct)
        parts.append(f"ogłoszenie jest {abs(difference):.0f}% {'powyżej' if difference > 0 else 'poniżej'} cennika")
    if signals.developer_first_price and signals.developer_first_price != signals.developer_price:
        parts.append(
            f"w cenniku od {signals.developer_first_seen:%Y-%m-%d}, pierwsza cena {_money(signals.developer_first_price)}"
        )
    if signals.developer_highest_price and signals.developer_highest_price > signals.developer_price:
        parts.append(f"najwyższa cena w cenniku {_money(signals.developer_highest_price)}")
    if signals.developer_price_with_extras and signals.developer_price_with_extras > signals.developer_price:
        parts.append(f"z obowiązkowymi składnikami {_money(signals.developer_price_with_extras)}")
    if signals.developer_extras:
        parts.append("dodatkowo w cenniku: " + "; ".join(signals.developer_extras))
    if signals.developer_unit_gone:
        parts.append(
            f"lokal zniknął z cennika po {signals.developer_last_seen:%Y-%m-%d}, może być już sprzedany lub zarezerwowany"
        )
    if signals.investment_units_listed is not None:
        parts.append(
            f"w inwestycji {signals.investment_units_listed} lokali w cenniku, {signals.investment_units_gone} zniknęło "
            f"od {signals.investment_tracked_since:%Y-%m}"
        )
    return ", ".join(parts)


def area_warnings_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.area_notes:
        return None
    return " ".join(signals.area_notes)


def nuisances_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.nuisance_notes:
        return None
    return "; ".join(signals.nuisance_notes)


def location_warnings_phrase(signals: Optional[AdMarketSignals]) -> Optional[str]:
    if signals is None or not signals.location_notes:
        return None
    return " ".join(signals.location_notes)


def _money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " zł"
