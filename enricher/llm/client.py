from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable


class LlmPermanentError(Exception):
    pass


class LlmRefusalError(LlmPermanentError):
    pass


class LlmResponseFormatError(Exception):
    pass


@dataclass(frozen=True)
class LlmImage:
    media_type: str
    url: Optional[str] = None
    base64_data: Optional[str] = None

    @property
    def data_uri(self) -> str:
        if self.base64_data is None:
            raise LlmResponseFormatError("Image has no base64 payload")
        return f"data:{self.media_type};base64,{self.base64_data}"


@dataclass(frozen=True)
class LlmRequest:
    model: str
    system_prompt: str
    user_prompt: str
    json_schema: dict
    schema_name: str
    max_output_tokens: int
    effort: Optional[str] = None
    images: tuple[LlmImage, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LlmResponse:
    payload: dict
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@runtime_checkable
class LlmClient(Protocol):
    @property
    def provider(self) -> str:
        ...

    def complete(self, request: LlmRequest) -> LlmResponse:
        ...
