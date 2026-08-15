from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

ANTHROPIC_PROVIDER = "anthropic"
OPENAI_PROVIDER = "openai"

DEFAULT_SCREENING_MODEL = "claude-haiku-4-5"
DEFAULT_EVALUATION_MODEL = "claude-sonnet-5"

_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})

_API_KEY_VARIABLE_BY_PROVIDER = {
    ANTHROPIC_PROVIDER: "ANTHROPIC_API_KEY",
    OPENAI_PROVIDER: "OPENAI_API_KEY",
}

_MODEL_PREFIXES_WITHOUT_EFFORT = ("claude-haiku", "claude-3", "claude-sonnet-4-5")
_EFFORT_DISABLED_VALUES = frozenset({"none", "off", "-"})
_DEFAULT_EFFORT = "medium"


def supports_effort(model: str) -> bool:
    return not any(model.startswith(prefix) for prefix in _MODEL_PREFIXES_WITHOUT_EFFORT)


@dataclass(frozen=True)
class ModelPricing:
    input_usd_per_million: float
    output_usd_per_million: float

    def cost_usd(
            self,
            input_tokens: int,
            output_tokens: int,
            cache_read_tokens: int = 0,
            cache_write_tokens: int = 0,
    ) -> float:
        per_input_token = self.input_usd_per_million / 1_000_000
        per_output_token = self.output_usd_per_million / 1_000_000
        return (
                input_tokens * per_input_token
                + cache_read_tokens * per_input_token * 0.1
                + cache_write_tokens * per_input_token * 1.25
                + output_tokens * per_output_token
        )


MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-haiku-4-5": ModelPricing(1.0, 5.0),
    "claude-sonnet-5": ModelPricing(3.0, 15.0),
    "claude-sonnet-4-6": ModelPricing(3.0, 15.0),
    "claude-opus-5": ModelPricing(5.0, 25.0),
    "claude-opus-4-8": ModelPricing(5.0, 25.0),
    "claude-fable-5": ModelPricing(10.0, 50.0),
}


def cost_usd_for(
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
) -> Optional[float]:
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    return pricing.cost_usd(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)


@dataclass(frozen=True)
class EnricherConfig:
    provider: str
    api_key: str
    base_url: Optional[str]
    screening_model: str
    evaluation_model: str
    max_images: int
    image_variant: str
    download_images: bool
    screening_effort: Optional[str]
    evaluation_effort: Optional[str]
    max_output_tokens: int
    price_drift_threshold: float
    daily_budget_usd: Optional[float]
    max_description_characters: int
    concurrency: int
    cycle_pause_seconds: int
    max_tries: int
    retry_pause_seconds: int

    @classmethod
    def from_env(cls) -> "EnricherConfig":
        load_dotenv()

        provider = os.environ.get("LLM_PROVIDER", ANTHROPIC_PROVIDER).strip().lower()
        if provider not in _API_KEY_VARIABLE_BY_PROVIDER:
            raise ValueError(
                f"LLM_PROVIDER must be one of {sorted(_API_KEY_VARIABLE_BY_PROVIDER)}, got '{provider}'"
            )

        api_key_variable = _API_KEY_VARIABLE_BY_PROVIDER[provider]
        api_key = os.environ.get(api_key_variable, "").strip()
        if not api_key:
            raise ValueError(
                f"Missing API key for provider '{provider}'. Set the {api_key_variable} environment variable."
            )

        image_variant = os.environ.get("LLM_IMAGE_VARIANT", "medium").strip().lower()
        if image_variant not in {"thumbnail", "small", "medium", "large"}:
            raise ValueError(
                f"LLM_IMAGE_VARIANT must be one of thumbnail/small/medium/large, got '{image_variant}'"
            )

        screening_model = os.environ.get("SCREENING_MODEL", DEFAULT_SCREENING_MODEL).strip()
        evaluation_model = os.environ.get("EVALUATION_MODEL", DEFAULT_EVALUATION_MODEL).strip()

        return cls(
            provider=provider,
            api_key=api_key,
            base_url=_read_optional("LLM_BASE_URL"),
            screening_model=screening_model,
            evaluation_model=evaluation_model,
            max_images=_read_int("LLM_MAX_IMAGES", 8),
            image_variant=image_variant,
            download_images=_read_bool("LLM_DOWNLOAD_IMAGES", False),
            screening_effort=_read_effort("SCREENING_EFFORT", screening_model),
            evaluation_effort=_read_effort("EVALUATION_EFFORT", evaluation_model),
            max_output_tokens=_read_int("LLM_MAX_OUTPUT_TOKENS", 8000),
            price_drift_threshold=_read_float("EVALUATION_PRICE_DRIFT_THRESHOLD", 0.05),
            daily_budget_usd=_read_optional_float("ENRICHER_DAILY_BUDGET_USD"),
            max_description_characters=_read_int("LLM_MAX_DESCRIPTION_CHARACTERS", 4000),
            concurrency=_read_int("ENRICHER_CONCURRENCY", 4),
            cycle_pause_seconds=_read_int("ENRICHER_CYCLE_PAUSE_SECONDS", 300),
            max_tries=_read_int("ENRICHER_MAX_TRIES", 3),
            retry_pause_seconds=_read_int("ENRICHER_RETRY_PAUSE_SECONDS", 10),
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


def _read_optional_float(name: str) -> Optional[float]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got '{value}'") from error


def _read_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got '{value}'") from error
