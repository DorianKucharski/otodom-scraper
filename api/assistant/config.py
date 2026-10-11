from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from llm.factory import LlmSettings
from llm.pricing import supports_effort

DEFAULT_INTERPRET_MODEL = "claude-haiku-4-5"
DEFAULT_RANK_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class AssistantConfig:
    llm: LlmSettings
    interpret_model: str
    rank_model: str
    rank_effort: Optional[str]
    daily_budget_usd: float
    candidates: int
    description_characters: int
    max_output_tokens: int

    @classmethod
    def from_env(cls) -> "AssistantConfig":
        rank_model = os.environ.get("ASSISTANT_RANK_MODEL", DEFAULT_RANK_MODEL).strip()
        effort = os.environ.get("ASSISTANT_RANK_EFFORT", "low").strip().lower()
        return cls(
            llm=LlmSettings.from_env(),
            interpret_model=os.environ.get("ASSISTANT_INTERPRET_MODEL", DEFAULT_INTERPRET_MODEL).strip(),
            rank_model=rank_model,
            rank_effort=effort if effort not in ("", "none") and supports_effort(rank_model) else None,
            daily_budget_usd=float(os.environ.get("ASSISTANT_DAILY_BUDGET_USD", "2") or 2),
            candidates=int(os.environ.get("ASSISTANT_CANDIDATES", "30") or 30),
            description_characters=int(os.environ.get("ASSISTANT_DESCRIPTION_CHARACTERS", "800") or 800),
            max_output_tokens=int(os.environ.get("ASSISTANT_MAX_OUTPUT_TOKENS", "8000") or 8000),
        )
