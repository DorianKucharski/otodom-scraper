from __future__ import annotations

import json
from typing import Optional

import anthropic

from .client import LlmImage, LlmPermanentError, LlmRefusalError, LlmRequest, LlmResponse, LlmResponseFormatError

_PROVIDER = "anthropic"

_PERMANENT_ERRORS = (
    anthropic.BadRequestError,
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.NotFoundError,
    anthropic.UnprocessableEntityError,
)


class AnthropicLlmClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.__client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

    @property
    def provider(self) -> str:
        return _PROVIDER

    def complete(self, request: LlmRequest) -> LlmResponse:
        try:
            response = self.__client.messages.create(
                model=request.model,
                max_tokens=request.max_output_tokens,
                system=[{
                    "type": "text",
                    "text": request.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                output_config=_output_config(request),
                messages=[{
                    "role": "user",
                    "content": [*_image_blocks(request.images), {"type": "text", "text": request.user_prompt}],
                }],
            )
        except _PERMANENT_ERRORS as error:
            raise LlmPermanentError(str(error)) from error

        if response.stop_reason == "refusal":
            raise LlmRefusalError(f"Model refused the request: {response.stop_details}")

        return LlmResponse(
            payload=_parse_payload(response),
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=response.usage.cache_read_input_tokens or 0,
            cache_write_tokens=response.usage.cache_creation_input_tokens or 0,
        )


def _output_config(request: LlmRequest) -> dict:
    output_config = {"format": {"type": "json_schema", "schema": request.json_schema}}
    if request.effort:
        output_config["effort"] = request.effort
    return output_config


def _image_blocks(images: tuple[LlmImage, ...]) -> list[dict]:
    return [_image_block(image) for image in images]


def _image_block(image: LlmImage) -> dict:
    if image.base64_data is not None:
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": image.media_type, "data": image.base64_data},
        }
    return {"type": "image", "source": {"type": "url", "url": image.url}}


def _parse_payload(response) -> dict:
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise LlmResponseFormatError(f"Response carries no text block, stop_reason={response.stop_reason}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise LlmResponseFormatError(f"Response is not valid JSON: {text[:500]}") from error
