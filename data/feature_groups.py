from __future__ import annotations

from data.models import Ad

FEATURE_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("Cechy", "features", "feature"),
    ("Wyposażenie", "flat_equipment", "equipment"),
    ("Dodatkowe powierzchnie", "flat_areas", "area"),
    ("Parking", "flat_parking", "parking"),
    ("Okna", "building_windows", "window_type"),
    ("Udogodnienia w budynku", "building_conveniences", "convenience"),
    ("Zabezpieczenia", "building_security", "security"),
)


def feature_values(ad: Ad, relation_name: str, value_attribute: str) -> tuple[str, ...]:
    return tuple(sorted(getattr(item, value_attribute) for item in getattr(ad, relation_name)))


def labelled_feature_groups(ad: Ad) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(
        (label, feature_values(ad, relation_name, value_attribute))
        for label, relation_name, value_attribute in FEATURE_GROUPS
    )


def all_feature_values(ad: Ad) -> tuple[str, ...]:
    return tuple(sorted(
        f"{relation_name}:{value}"
        for _, relation_name, value_attribute in FEATURE_GROUPS
        for value in feature_values(ad, relation_name, value_attribute)
    ))
