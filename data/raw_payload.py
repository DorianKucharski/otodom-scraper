from __future__ import annotations

import json
import zlib
from datetime import datetime
from typing import Optional

from .models import AdRawPayload

_COMPRESSION_LEVEL = 6


def compress_payload(payload: dict) -> bytes:
    return zlib.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(), _COMPRESSION_LEVEL)


def decompress_payload(blob: bytes) -> dict:
    return json.loads(zlib.decompress(blob))


def as_page_json(payload: dict) -> dict:
    return {"props": {"pageProps": payload}}


def raw_payload_row(ad_id: int, payload: Optional[dict], scraped_at: datetime) -> Optional[AdRawPayload]:
    if not payload:
        return None
    return AdRawPayload(ad_id=ad_id, payload=compress_payload(payload), scraped_at=scraped_at)
