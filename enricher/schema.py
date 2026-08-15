from __future__ import annotations

SCORE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    (
        "overall_score",
        "Ocena ogolna 1-10: jak bardzo warto pojechac obejrzec to mieszkanie, po zwazeniu wszystkich pozostalych "
        "kryteriow. 1 = strata czasu, 10 = wyjatkowa okazja.",
    ),
    (
        "finish_quality_score",
        "Jakosc wykonczenia widoczna na zdjeciach: materialy, stolarka, lazienka, kuchnia, spojnosc wykonania. "
        "1 = stan surowy lub partactwo, 5 = poprawny standard deweloperski lub przecietny remont, "
        "10 = wysoki standard, dobre materialy, dopracowane detale.",
    ),
    (
        "freshness_score",
        "Swiezosc wykonczenia niezaleznie od jego jakosci: jak dawno temu to remontowano. "
        "1 = wystroj sprzed dekad, zniszczony, 5 = kilkanascie lat, zuzyty ale zadbany, 10 = nowe lub swiezo po remoncie.",
    ),
    (
        "move_in_readiness_score",
        "Gotowosc do wprowadzenia sie od reki. 1 = stan surowy, brak tynkow, instalacji, podlog, "
        "5 = wymaga odswiezenia i wlasnych mebli, 10 = mozna wejsc z walizka.",
    ),
    (
        "layout_score",
        "Funkcjonalnosc rozkladu: proporcje pomieszczen, brak przechodnich pokoi, sensowna kuchnia, miejsce do "
        "przechowywania, brak zmarnowanej powierzchni. 1 = rozklad odpadajacy, 10 = wzorowy.",
    ),
    (
        "natural_light_score",
        "Doswietlenie i ekspozycja: wielkosc okien, jasnosc wnetrza na zdjeciach, widok z okna, pietro. "
        "1 = ciemna nora, 10 = bardzo jasne wnetrze.",
    ),
    (
        "building_condition_score",
        "Stan budynku i czesci wspolnych widoczny na zdjeciach i wynikajacy z danych: elewacja, klatka, wiek, "
        "technologia, winda. 1 = ruina, 10 = nowy lub kompleksowo zmodernizowany budynek.",
    ),
    (
        "location_score",
        "Ocena lokalizacji na podstawie adresu, dzielnicy i odleglosci od centrum oraz tego, co pisze ogloszenie o "
        "okolicy. 1 = zla lokalizacja, 10 = bardzo dobra.",
    ),
    (
        "value_for_money_score",
        "Oplacalnosc: ile mieszkanie daje w stosunku do ceny, z uwzglednieniem mediany ceny za m2 w dzielnicy "
        "podanej w danych rynkowych, metrazu, czynszu i stanu. 1 = razaco przeplacone, 5 = cena rynkowa, "
        "10 = wyraznie ponizej wartosci.",
    ),
    (
        "photo_trust_score",
        "Na ile zdjecia pozwalaja ocenic mieszkanie. 1 = rendery, wizualizacje, home staging, puste mury, zdjecia "
        "tylko z zewnatrz albo dwa zdjecia bez lazienki i kuchni, 10 = pelna, uczciwa dokumentacja stanu faktycznego.",
    ),
)

SCORE_FIELD_NAMES: tuple[str, ...] = tuple(name for name, _ in SCORE_DEFINITIONS)

RENOVATION_NEEDED_VALUES: tuple[str, ...] = ("none", "cosmetic", "partial", "full")

STYLE_TAG_VALUES: tuple[str, ...] = (
    "MODERN",
    "SCANDINAVIAN",
    "MINIMALIST",
    "CLASSIC",
    "RUSTIC",
    "INDUSTRIAL",
    "GLAMOUR",
    "DATED",
    "WORN",
    "RAW",
    "UNKNOWN",
)

SCREENING_STATUS_VALUES: tuple[str, ...] = ("passed", "rejected")

_SCORE_RANGE = list(range(1, 11))


def _attribute_array_property(description: str) -> dict:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Nazwa cechy w snake_case, po angielsku."},
                "value": {"type": "string", "description": "Wartosc cechy jako tekst."},
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
    }


def _object_schema(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


SCREENING_SCHEMA: dict = _object_schema({
    "status": {
        "type": "string",
        "enum": list(SCREENING_STATUS_VALUES),
        "description": "'rejected' tylko gdy ogloszenie spelnia ktores z twardych kryteriow odrzucenia, "
                       "w kazdym innym wypadku 'passed'.",
    },
    "rejection_reason": {
        "type": "string",
        "description": "Jedno zdanie po polsku uzasadniajace odrzucenie. Pusty string gdy status to 'passed'.",
    },
    "extracted_attributes": _attribute_array_property(
        "Fakty wprost napisane w opisie, a nieobecne na liscie cech z serwisu. Tylko to, co ogloszenie "
        "faktycznie stwierdza, bez zgadywania."
    ),
})

EVALUATION_SCHEMA: dict = _object_schema({
    **{
        name: {"type": "integer", "enum": _SCORE_RANGE, "description": description}
        for name, description in SCORE_DEFINITIONS
    },
    "renovation_needed": {
        "type": "string",
        "enum": list(RENOVATION_NEEDED_VALUES),
        "description": "Zakres prac potrzebnych przed zamieszkaniem: none = zadne, cosmetic = odswiezenie i "
                       "malowanie, partial = remont czesci pomieszczen lub instalacji, full = remont generalny "
                       "albo wykonczenie od zera.",
    },
    "style_tag": {
        "type": "string",
        "enum": list(STYLE_TAG_VALUES),
        "description": "Dominujacy charakter wystroju. RAW dla stanu surowego, UNKNOWN gdy zdjecia nie pozwalaja ocenic.",
    },
    "summary": {
        "type": "string",
        "description": "Dwa do trzech zdan po polsku: co to za mieszkanie, w jakim jest stanie i dla kogo ma sens. "
                       "Konkretnie, bez ogolnikow z ogloszenia.",
    },
    "strengths": {
        "type": "array",
        "description": "Od dwoch do pieciu najmocniejszych stron, kazda jako krotkie haslo po polsku.",
        "items": {"type": "string"},
    },
    "concerns": {
        "type": "array",
        "description": "Od zera do szesciu zastrzezen i sygnalow ostrzegawczych, kazde jako krotkie haslo po polsku. "
                       "Tu trafia to, co odradza obejrzenie: brak tynkow, slad zawilgocenia, rozklad przechodni, "
                       "wysoki czynsz, zdjecia ukrywajace czesc mieszkania.",
        "items": {"type": "string"},
    },
    "attributes": _attribute_array_property(
        "Fakty odczytane ze zdjec i opisu, ktorych nie ma w danych strukturalnych: rodzaj kuchni, liczba lazienek, "
        "rodzaj podlog, stolarka okienna, stan lazienki, obecnosc balkonu, widok z okna, obecnosc mebli."
    ),
})
