from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

_BLANK_LINES = re.compile(r"\n{3,}")
_TRUNCATION_MARKER = "\n[...opis skrócony]"
_BLOCK_LEVEL_TAGS = ("p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "section")


def plain_description(description: Optional[str], max_characters: Optional[int] = None) -> Optional[str]:
    if not description:
        return None

    soup = BeautifulSoup(description, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for block in soup.find_all(_BLOCK_LEVEL_TAGS):
        block.append("\n")

    text = _BLANK_LINES.sub("\n\n", soup.get_text("")).strip() or None
    if text is None or max_characters is None or len(text) <= max_characters:
        return text
    return text[:max_characters].rstrip() + _TRUNCATION_MARKER
