from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_MODEL_PREFIXES_WITHOUT_EFFORT = ("claude-haiku", "claude-3", "claude-sonnet-4-5")
_SNAPSHOT_DATE_SUFFIX = re.compile(r"-\d{8}$")


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
    pricing = MODEL_PRICING.get(model) or MODEL_PRICING.get(_SNAPSHOT_DATE_SUFFIX.sub("", model))
    if pricing is None:
        return None
    return pricing.cost_usd(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
