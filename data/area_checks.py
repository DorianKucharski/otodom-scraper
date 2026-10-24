from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

USABLE_AREA_SMALLER = "usable_area_smaller"
ATTIC_SLOPES = "attic_slopes"
APPURTENANT_INCLUDED = "appurtenant_included"

MIN_DIFFERENCE = 0.05
MIN_SHARE_OF_LISTED = 0.45

AREA_TEXT_PATTERN = r"(użytkow|podłodze|skos|wliczon|w tym (piwnic|komórk|garaż|strych|pomieszcz))"

_NUMBER = r"(\d{2,3}(?:[.,]\d{1,2})?)"
_UNIT = r"(?:m2|m²|mkw\.?|m\.\s?kw\.?|metr\w*)"
_USABLE = r"(?:powierzchni\w*\s+użytkow\w*|pow\.\s*użytk\w*|użytkow\w*|po\s+podłodze)"
_USABLE_AFTER_NUMBER = re.compile(rf"{_NUMBER}\s*{_UNIT}\s*[(,–-]?\s*{_USABLE}", re.IGNORECASE)
_USABLE_BEFORE_NUMBER = re.compile(rf"{_USABLE}[^0-9]{{0,25}}{_NUMBER}\s*{_UNIT}", re.IGNORECASE)
_PART_OF_FLAT = re.compile(
    r"(poziom|parter|piętr|pokój|pokoj|kuchni|salon|sypialn|łazienk|antresol|strych|piwnic|garaż|działk|ogród|ogrod|taras)\w*[^.]{0,40}$",
    re.IGNORECASE,
)
_SLOPES = re.compile(r"\bskos\w*|\bpo\s+podłodze", re.IGNORECASE)
_APPURTENANT = re.compile(
    r"\b(?:wliczon\w*|w\s+tym)\s+(?:\w+\s+){0,2}(?:piwnic\w*|komórk\w*|garaż\w*|strych\w*|pomieszczeni\w*\s+gospodarcz\w*)",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


@dataclass
class AreaVerdict:
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, flag: str, note: str):
        if flag not in self.flags:
            self.flags.append(flag)
            self.notes.append(note)


def area_verdict(area: Optional[float], title: Optional[str], description: Optional[str]) -> AreaVerdict:
    verdict = AreaVerdict()
    content = re.sub(r"\s+", " ", _TAG.sub(" ", " ".join(part for part in (title, description) if part))).strip()
    if not content:
        return verdict

    usable = _usable_area(content, area)
    if usable is not None:
        verdict.add(
            USABLE_AREA_SMALLER,
            f"Opis podaje {_area(usable)} powierzchni użytkowej, a ogłoszenie {_area(area)}. "
            f"Cena za metr użytkowy jest o {round((area / usable - 1) * 100)}% wyższa.",
        )

    slopes = _SLOPES.search(content)
    if slopes:
        verdict.add(ATTIC_SLOPES, f"Opis wspomina skosy albo powierzchnię po podłodze: „{_excerpt(content, slopes)}”.")

    appurtenant = _APPURTENANT.search(content)
    if appurtenant:
        verdict.add(APPURTENANT_INCLUDED, f"Metraż może obejmować pomieszczenia przynależne: „{_excerpt(content, appurtenant)}”.")

    return verdict


def _usable_area(content: str, area: Optional[float]) -> Optional[float]:
    if not area:
        return None
    candidates = []
    for pattern in (_USABLE_AFTER_NUMBER, _USABLE_BEFORE_NUMBER):
        for match in pattern.finditer(content):
            if _PART_OF_FLAT.search(content[max(0, match.start() - 25):match.start()]):
                continue
            value = float(match.group(1).replace(",", "."))
            if MIN_SHARE_OF_LISTED * area <= value < area * (1 - MIN_DIFFERENCE):
                candidates.append(value)
    return min(candidates) if candidates else None


def _area(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " m²"


def _excerpt(content: str, match: re.Match, margin: int = 50) -> str:
    left = max(content.rfind(" ", 0, max(match.start() - margin, 0)) + 1, 0)
    right = content.find(" ", min(match.end() + margin, len(content)))
    right = len(content) if right == -1 else right
    return ("…" if left > 0 else "") + content[left:right].strip() + ("…" if right < len(content) else "")
