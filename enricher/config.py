from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from llm.factory import LlmSettings
from llm.pricing import supports_effort

DEFAULT_SCREENING_MODEL = "claude-haiku-4-5"
DEFAULT_EVALUATION_MODEL = "claude-sonnet-5"

_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})
_EFFORT_DISABLED_VALUES = frozenset({"none", "off", "-"})
_DEFAULT_EFFORT = "medium"


@dataclass(frozen=True)
class EnricherConfig:
    llm: LlmSettings
    screening_model: str
    evaluation_model: str
    max_images: int
    image_variant: str
    download_images: bool
    screening_effort: Optional[str]
    evaluation_effort: Optional[str]
    max_output_tokens: int
    price_drift_threshold: float
    daily_budget_usd: float
    request_daily_budget_usd: float
    max_description_characters: int
    concurrency: int
    cycle_pause_seconds: int
    max_tries: int
    retry_pause_seconds: int
    market_signals_interval_hours: float
    rcn_cities: tuple[str, ...]
    rcn_refresh_days: float
    developer_prices_refresh_hours: float

    @classmethod
    def from_env(cls) -> "EnricherConfig":
        llm = LlmSettings.from_env()

        image_variant = os.environ.get("LLM_IMAGE_VARIANT", "medium").strip().lower()
        if image_variant not in {"thumbnail", "small", "medium", "large"}:
            raise ValueError(
                f"LLM_IMAGE_VARIANT must be one of thumbnail/small/medium/large, got '{image_variant}'"
            )

        screening_model = os.environ.get("SCREENING_MODEL", DEFAULT_SCREENING_MODEL).strip()
        evaluation_model = os.environ.get("EVALUATION_MODEL", DEFAULT_EVALUATION_MODEL).strip()

        return cls(
            llm=llm,
            screening_model=screening_model,
            evaluation_model=evaluation_model,
            max_images=_read_int("LLM_MAX_IMAGES", 8),
            image_variant=image_variant,
            download_images=_read_bool("LLM_DOWNLOAD_IMAGES", False),
            screening_effort=_read_effort("SCREENING_EFFORT", screening_model),
            evaluation_effort=_read_effort("EVALUATION_EFFORT", evaluation_model),
            max_output_tokens=_read_int("LLM_MAX_OUTPUT_TOKENS", 8000),
            price_drift_threshold=_read_float("EVALUATION_PRICE_DRIFT_THRESHOLD", 0.05),
            daily_budget_usd=_read_float("ENRICHER_DAILY_BUDGET_USD", 10.0),
            request_daily_budget_usd=_read_float("ENRICHER_REQUEST_DAILY_BUDGET_USD", 3.0),
            max_description_characters=_read_int("LLM_MAX_DESCRIPTION_CHARACTERS", 4000),
            concurrency=_read_int("ENRICHER_CONCURRENCY", 4),
            cycle_pause_seconds=_read_int("ENRICHER_CYCLE_PAUSE_SECONDS", 300),
            max_tries=_read_int("ENRICHER_MAX_TRIES", 3),
            retry_pause_seconds=_read_int("ENRICHER_RETRY_PAUSE_SECONDS", 10),
            market_signals_interval_hours=_read_float("MARKET_SIGNALS_INTERVAL_HOURS", 6.0),
            rcn_cities=tuple(city.strip() for city in os.environ.get("RCN_CITIES", "").split(",") if city.strip()),
            rcn_refresh_days=_read_float("RCN_REFRESH_DAYS", 30.0),
            developer_prices_refresh_hours=_read_float("DEVELOPER_PRICES_REFRESH_HOURS", 24.0),
        )


def _read_effort(stage_variable: str, model: str) -> Optional[str]:
    stage_effort = _read_optional(stage_variable)
    if stage_effort is not None:
        return _parsed_effort(stage_effort)

    if not supports_effort(model):
        return None

    return _parsed_effort(os.environ.get("LLM_EFFORT", _DEFAULT_EFFORT))


def _parsed_effort(value: str) -> Optional[str]:
    normalized = value.strip().lower()
    return None if normalized in _EFFORT_DISABLED_VALUES or not normalized else normalized


def _read_optional(name: str) -> Optional[str]:
    value = os.environ.get(name, "").strip()
    return value or None


def _read_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in _TRUTHY_VALUES


def _read_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got '{value}'") from error


def _read_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got '{value}'") from error
