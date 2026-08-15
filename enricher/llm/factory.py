from __future__ import annotations

from ..config import ANTHROPIC_PROVIDER, EnricherConfig, OPENAI_PROVIDER
from .anthropic_client import AnthropicLlmClient
from .client import LlmClient
from .openai_client import OpenAiLlmClient


def build_llm_client(config: EnricherConfig) -> LlmClient:
    if config.provider == ANTHROPIC_PROVIDER:
        return AnthropicLlmClient(api_key=config.api_key, base_url=config.base_url)
    if config.provider == OPENAI_PROVIDER:
        return OpenAiLlmClient(api_key=config.api_key, base_url=config.base_url)
    raise ValueError(f"Unsupported LLM_PROVIDER: {config.provider}")
