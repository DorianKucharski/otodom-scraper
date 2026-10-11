from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ValueLabel:
    label: str
    description: Optional[str] = None


OFFER_TYPES = {
    "SALE": ValueLabel("Kupno"),
    "RENT": ValueLabel("Wynajem", "Cena to miesięczny czynsz najmu."),
}

OBJECT_TYPES = {
    "APARTMENT": ValueLabel("Mieszkanie"),
    "HOUSE": ValueLabel("Dom"),
}

BUILDING_TYPES = {
    "BLOCK": ValueLabel("Blok", "Budynek wielorodzinny z wieloma klatkami, najczęściej z PRL lub lat 90."),
    "APARTMENT": ValueLabel("Apartamentowiec", "Nowszy budynek wielorodzinny, zwykle z windą, halą garażową i ochroną."),
    "TENEMENT": ValueLabel("Kamienica", "Stara zabudowa miejska, najczęściej sprzed 1939 r., wysokie sufity."),
    "DETACHED": ValueLabel("Dom wolnostojący"),
    "SEMI_DETACHED": ValueLabel("Bliźniak", "Dom, który dzieli jedną ścianę z sąsiednim."),
    "RIBBON": ValueLabel("Szeregowiec", "Dom w rzędzie, ze wspólnymi ścianami z sąsiadami po obu stronach."),
    "HOUSE": ValueLabel("Dom"),
    "INFILL": ValueLabel("Plomba", "Budynek wstawiony w lukę między istniejącymi kamienicami."),
    "FARM": ValueLabel("Siedlisko", "Dom na wsi z działką rolną."),
    "LOFT": ValueLabel("Loft", "Mieszkanie w przebudowanym budynku poprzemysłowym."),
    "RESIDENCE": ValueLabel("Rezydencja"),
    "OTHER": ValueLabel("Inny"),
}

BUILDING_MATERIALS = {
    "BRICK": ValueLabel("Cegła", "Tradycyjny mur. Trwały, dobrze tłumi dźwięk i trzyma ciepło."),
    "BREEZEBLOCK": ValueLabel("Pustak", "Bloczki ceramiczne lub betonowe. Najczęstszy materiał nowych budynków."),
    "CONCRETE_PLATE": ValueLabel(
        "Wielka płyta",
        "Prefabrykowane płyty betonowe, typowe dla bloków z lat 60-80. Słabsza akustyka i izolacja.",
    ),
    "SILIKAT": ValueLabel("Silikat", "Bloczki wapienno-piaskowe. Bardzo dobrze tłumią dźwięk, częste w nowych blokach."),
    "REINFORCED_CONCRETE": ValueLabel("Żelbet", "Beton zbrojony, szkielet nowych i wysokich budynków."),
    "CELLULAR_CONCRETE": ValueLabel(
        "Beton komórkowy", "Lekkie bloczki (np. Ytong, Solbet). Ciepłe, ale słabiej tłumią dźwięk."
    ),
    "CONCRETE": ValueLabel("Beton"),
    "WOOD": ValueLabel("Drewno", "Dom drewniany albo w konstrukcji szkieletowej."),
    "HYDROTON": ValueLabel("Keramzyt", "Bloczki z keramzytobetonu (hydroton). Lekkie i ciepłe."),
    "OTHER": ValueLabel("Inny"),
}

BUILDING_HEATING = {
    "URBAN": ValueLabel("Miejskie", "Z miejskiej sieci ciepłowniczej, bez pieca w mieszkaniu."),
    "GAS": ValueLabel("Gazowe", "Własny kocioł gazowy w mieszkaniu lub domu."),
    "BOILER_ROOM": ValueLabel("Kotłownia", "Wspólna kotłownia budynku lub osiedla."),
    "ELECTRICAL": ValueLabel("Elektryczne", "Grzejniki elektryczne. Wygodne, ale zwykle drogie w użyciu."),
    "TILED_STOVE": ValueLabel("Piece kaflowe", "Piec na węgiel lub drewno w mieszkaniu, do palenia ręcznie."),
    "OTHER": ValueLabel("Inne"),
}

MARKETS = {
    "PRIMARY": ValueLabel("Pierwotny", "Nowe mieszkanie od dewelopera."),
    "SECONDARY": ValueLabel("Wtórny", "Używane mieszkanie od poprzedniego właściciela."),
    "ALL": ValueLabel("Bez podziału", "Tak otodom oznacza ogłoszenia wynajmu."),
    "": ValueLabel("Nie podano"),
}

ADVERTISER_TYPES = {
    "business": ValueLabel("Biuro lub deweloper", "Agencja nieruchomości albo deweloper, zwykle z prowizją."),
    "private": ValueLabel("Osoba prywatna", "Bezpośrednio od właściciela, bez prowizji."),
}

PROPERTY_CONDITIONS = {
    "READY_TO_USE": ValueLabel("Do zamieszkania"),
    "TO_COMPLETION": ValueLabel("Do wykończenia", "Stan deweloperski: bez podłóg, drzwi i białego montażu."),
    "TO_RENOVATION": ValueLabel("Do remontu"),
}

PROPERTY_OWNERSHIP = {
    "FULL_OWNERSHIP": ValueLabel("Pełna własność", "Odrębna własność lokalu z własną księgą wieczystą."),
    "LIMITED_OWNERSHIP": ValueLabel(
        "Spółdzielcze własnościowe", "Prawo do lokalu w spółdzielni. Można sprzedać i odziedziczyć."
    ),
    "SHARE": ValueLabel("Udział", "Część współwłasności, nie całe mieszkanie."),
    "USUFRUCT": ValueLabel("Użytkowanie"),
}

PROPERTY_TYPES = {
    "FLAT": ValueLabel("Mieszkanie"),
}

STYLE_TAGS = {
    "MODERN": ValueLabel("Nowoczesny"),
    "SCANDINAVIAN": ValueLabel("Skandynawski"),
    "MINIMALIST": ValueLabel("Minimalistyczny"),
    "CLASSIC": ValueLabel("Klasyczny"),
    "INDUSTRIAL": ValueLabel("Industrialny"),
    "GLAMOUR": ValueLabel("Glamour"),
    "RUSTIC": ValueLabel("Rustykalny"),
    "DATED": ValueLabel("Przestarzały", "Wnętrze z poprzednich dekad, do odświeżenia."),
    "WORN": ValueLabel("Zniszczony"),
    "RAW": ValueLabel("Surowy", "Stan deweloperski albo pustostan."),
    "UNKNOWN": ValueLabel("Nieokreślony"),
}

RENOVATION_NEEDED = {
    "none": ValueLabel("Nic do zrobienia"),
    "cosmetic": ValueLabel("Odświeżenie", "Malowanie, drobne poprawki."),
    "partial": ValueLabel("Remont częściowy", "Np. łazienka albo kuchnia."),
    "full": ValueLabel("Remont generalny", "Instalacje, podłogi, łazienka, kuchnia."),
}

_FEATURE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "balkon": ("balkon", "balcony"),
    "taras": ("taras", "terrace"),
    "ogródek": ("ogródek", "garden"),
    "piwnica": ("piwnica", "basement"),
    "pomieszczenie użytkowe": ("pom. użytkowe", "usable_room"),
    "strych": ("strych",),
    "oddzielna kuchnia": ("oddzielna kuchnia",),
    "mieszkanie dwupoziomowe": ("dwupoziomowe",),
    "garaż / miejsce parkingowe": ("garaż/miejsce parkingowe", "garage", "garaż"),
    "winda": ("winda", "LIFT"),
    "domofon / wideofon": ("domofon / wideofon", "ENTRYPHONE"),
    "monitoring / ochrona": ("monitoring / ochrona", "MONITORING"),
    "teren zamknięty": ("teren zamknięty", "CLOSED_AREA"),
    "drzwi / okna antywłamaniowe": ("drzwi / okna antywłamaniowe", "ANTI_BURGLARY_DOOR"),
    "rolety antywłamaniowe": ("rolety antywłamaniowe", "ROLLER_SHUTTERS"),
    "system alarmowy": ("system alarmowy", "ALARM"),
    "internet": ("internet", "INTERNET"),
    "telewizja kablowa": ("telewizja kablowa",),
    "telefon": ("telefon",),
    "klimatyzacja": ("klimatyzacja", "air_conditioning"),
    "meble": ("meble", "furniture", "umeblowanie"),
    "lodówka": ("lodówka", "fridge"),
    "piekarnik": ("piekarnik", "oven"),
    "kuchenka": ("kuchenka", "stove"),
    "pralka": ("pralka", "washing_machine"),
    "zmywarka": ("zmywarka", "dishwasher"),
    "telewizor": ("telewizor", "tv"),
    "basen": ("basen",),
    "okna plastikowe": ("PLASTIC",),
    "okna drewniane": ("WOODEN",),
    "okna aluminiowe": ("ALUMINIUM",),
    "również dla studentów": ("Wynajmę również studentom",),
    "tylko dla niepalących": ("tylko dla niepalących",),
    "dom parterowy": ("Dom parterowy",),
    "dom rekreacyjny": ("Rekreacyjny",),
    "media: prąd": ("prąd",),
    "media: woda": ("woda",),
    "media: gaz": ("gaz",),
    "media: kanalizacja": ("kanalizacja",),
    "media: szambo": ("szambo",),
    "media: przydomowa oczyszczalnia": ("oczyszczalnia",),
    "ogrzewanie gazowe": ("gazowe",),
    "ogrzewanie węglowe": ("węglowe",),
    "ogrzewanie kominkowe": ("kominkowe",),
    "ogrzewanie elektryczne": ("elektryczne",),
    "ogrzewanie olejowe": ("olejowe",),
    "ogrzewanie miejskie": ("miejskie",),
    "ogrzewanie piecami kaflowymi": ("piece kaflowe",),
    "ogrzewanie biomasą": ("biomasa",),
    "pompa ciepła": ("pompa ciepła",),
    "geotermia": ("geotermika",),
    "kolektor słoneczny": ("kolektor słoneczny",),
    "dojazd asfaltowy": ("asfaltowy",),
    "dojazd utwardzony": ("utwardzony",),
    "dojazd polny": ("polny",),
    "ogrodzenie z siatki": ("siatka",),
    "ogrodzenie murowane": ("murowane",),
    "ogrodzenie metalowe": ("metalowe",),
    "ogrodzenie drewniane": ("drewniane",),
    "ogrodzenie betonowe": ("betonowe",),
    "żywopłot": ("żywopłot",),
    "w okolicy: las": ("las",),
    "w okolicy: jezioro": ("jezioro",),
    "w okolicy: góry": ("góry",),
    "w okolicy: morze": ("morze",),
}

FEATURE_LABEL_BY_VALUE: dict[str, str] = {
    raw: label for label, raws in _FEATURE_SYNONYMS.items() for raw in raws
}


def label_of(labels: dict[str, ValueLabel], value: Optional[str]) -> Optional[ValueLabel]:
    if value is None:
        return None
    return labels.get(value) or ValueLabel(humanize(value))


def display_label(labels: dict[str, ValueLabel], value: Optional[str]) -> Optional[str]:
    label = label_of(labels, value)
    return label.label if label else None


def feature_label(value: str) -> str:
    return FEATURE_LABEL_BY_VALUE.get(value, value)


def feature_values_for(selected: str) -> list[str]:
    label = feature_label(selected)
    return sorted({selected, *_FEATURE_SYNONYMS.get(label, ())})


def humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()
