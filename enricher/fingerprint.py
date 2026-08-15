from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from data.models import Ad
from data.feature_groups import all_feature_values

_SEPARATOR = b"\x1f"


def content_fingerprint(ad: Ad) -> str:
    digest = hashlib.sha256()
    for part in _fingerprint_parts(ad):
        digest.update((part or "").encode("utf-8"))
        digest.update(_SEPARATOR)
    return digest.hexdigest()


def has_price_drifted(current_price: Optional[int], evaluated_price: Optional[int], threshold: float) -> bool:
    if not current_price or not evaluated_price:
        return True
    return abs(current_price - evaluated_price) / evaluated_price > threshold


def _fingerprint_parts(ad: Ad) -> Iterable[str]:
    yield ad.title
    yield ad.description
    yield str(ad.area_value)
    yield str(ad.flat_number_of_rooms)
    yield str(ad.flat_floor)
    yield str(ad.building_year)
    yield str(ad.property_condition)
    yield from all_feature_values(ad)
    yield from sorted(image.large for image in ad.images)
