from __future__ import annotations

import json
import re
from datetime import date
from typing import Iterator, Optional

from lxml import etree

LINKED_FORMATS = ("csv", "xlsx", "json", "xml")

_HISTORY_KEY = re.compile(r"histor|zmian|changes|previous", re.IGNORECASE)
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, recover=True)

Record = dict[str, object]


def harvester_link(content: bytes, data_date: Optional[date]) -> Optional[tuple[str, str]]:
    root = _xml_root(content)
    if root is None:
        return None
    links = []
    for resource in root.iter("{*}resource"):
        url = (resource.findtext("{*}url") or "").strip()
        file_format = url.rsplit("?", 1)[0].rsplit(".", 1)[-1].lower()
        day = _iso_date(resource.findtext("{*}dataDate"))
        if url.startswith("http") and file_format in LINKED_FORMATS and file_format != "xml":
            links.append((day or date.min, url, file_format))
    if not links:
        return None
    on_or_before = [link for link in links if data_date is None or link[0] <= data_date]
    _, url, file_format = max(on_or_before or links)
    return url, file_format


def json_rows(content: bytes) -> list[list]:
    try:
        data = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return []
    return rows_of(list(leaf_records(data)))


def xml_rows(content: bytes) -> list[list]:
    root = _xml_root(content)
    if root is None:
        return []
    return rows_of(list(leaf_records(_tree_of(root))))


def leaf_records(node, context: Optional[Record] = None, path: str = "") -> Iterator[Record]:
    context = context or {}
    if isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                yield from leaf_records(item, context, path)
        return
    if not isinstance(node, dict):
        return
    own: Record = {}
    children: list[tuple[str, list]] = []
    _split(node, path, own, children)
    if not children:
        if own:
            yield {**context, **own}
        return
    merged = {**context, **own}
    for child_path, items in children:
        yield from leaf_records(items, merged, child_path)


def rows_of(records: list[Record]) -> list[list]:
    if not records:
        return []
    headers: dict[str, None] = {}
    for record in records:
        for key in record:
            headers.setdefault(key, None)
    keys = list(headers)
    return [keys] + [[record.get(key) for key in keys] for record in records]


def _split(node: dict, path: str, own: Record, children: list[tuple[str, list]]):
    for key, value in node.items():
        key_path = f"{path} {_words(key)}".strip()
        if isinstance(value, dict):
            _split(value, key_path, own, children)
        elif isinstance(value, list):
            if any(isinstance(item, dict) for item in value):
                if not _HISTORY_KEY.search(str(key)):
                    children.append((key_path, value))
            elif value:
                own[key_path] = ", ".join(str(item) for item in value)
        elif value is not None:
            own[key_path] = value


def _tree_of(element) -> object:
    children = [child for child in element if isinstance(child.tag, str)]
    attributes = {name.rsplit("}", 1)[-1].rsplit(":", 1)[-1]: value for name, value in element.attrib.items()}
    if not children:
        text = (element.text or "").strip()
        if attributes and text:
            return {**attributes, "value": text}
        return attributes or text
    tree: dict[str, object] = dict(attributes)
    counts: dict[str, int] = {}
    for child in children:
        counts[_local(child.tag)] = counts.get(_local(child.tag), 0) + 1
    for child in children:
        name = _local(child.tag)
        value = _tree_of(child)
        if counts[name] > 1:
            tree.setdefault(name, []).append(value)
        else:
            tree[name] = value
    return tree


def _local(tag: str) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def _words(key: str) -> str:
    return re.sub(r"(?<=[a-ząćęłńóśźż0-9])(?=[A-ZĄĆĘŁŃÓŚŹŻ])", " ", str(key)).replace("_", " ").strip()


def _xml_root(content: bytes):
    try:
        root = etree.fromstring(content, _PARSER)
    except (etree.XMLSyntaxError, ValueError):
        return None
    return root


def _iso_date(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None
