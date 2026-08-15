from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

_BLANK_LINES = re.compile(r"\n{3,}")
_BLOCK_LEVEL_TAGS = ("p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "table", "tr", "section")


def plain_description(description: Optional[str]) -> Optional[str]:
    if not description:
        return None

    soup = BeautifulSoup(description, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for block in soup.find_all(_BLOCK_LEVEL_TAGS):
        block.append("\n")

    return _BLANK_LINES.sub("\n\n", soup.get_text("")).strip() or None
