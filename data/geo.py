from __future__ import annotations

import math

METRES_PER_DEGREE = 111_320


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2)
    return math.hypot((lat2 - lat1) * METRES_PER_DEGREE, (lon2 - lon1) * METRES_PER_DEGREE * math.cos(mean_lat))


def excerpt(content: str, start: int, end: int, margin: int = 50) -> str:
    left = max(content.rfind(" ", 0, max(start - margin, 0)) + 1, 0)
    right = content.find(" ", min(end + margin, len(content)))
    right = len(content) if right == -1 else right
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(content) else ""
    return f"{prefix}{content[left:right].strip()}{suffix}"

