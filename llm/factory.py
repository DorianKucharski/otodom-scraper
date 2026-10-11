from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from .anthropic_client import AnthropicLlmClient
from .client import LlmClient
from .openai_client import OpenAiLlmClient

ANTHROPIC_PROVIDER = "anthropic"
OPENAI_PROVIDER = "openai"

_API_KEY_VARIABLE_BY_PROVIDER = {
    ANTHROPIC_PROVIDER: "ANTHROPIC_API_KEY",
    OPENAI_PROVIDER: "OPENAI_API_KEY",
}


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    api_key: str
    base_url: Optional[str]

    @classmethod
    def from_env(cls) -> "LlmSettings":
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

        return cls(provider=provider, api_key=api_key, base_url=os.environ.get("LLM_BASE_URL", "").strip() or None)


def build_llm_client(settings: LlmSettings) -> LlmClient:
    if settings.provider == ANTHROPIC_PROVIDER:
        return AnthropicLlmClient(api_key=settings.api_key, base_url=settings.base_url)
    if settings.provider == OPENAI_PROVIDER:
        return OpenAiLlmClient(api_key=settings.api_key, base_url=settings.base_url)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.provider}")
