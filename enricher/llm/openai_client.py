from __future__ import annotations

import json
from typing import Optional

import openai
from openai import OpenAI

from .client import LlmImage, LlmPermanentError, LlmRefusalError, LlmRequest, LlmResponse, LlmResponseFormatError

_PROVIDER = "openai"

_PERMANENT_ERRORS = (
    openai.BadRequestError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.UnprocessableEntityError,
)


class OpenAiLlmClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.__client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def provider(self) -> str:
        return _PROVIDER

    def complete(self, request: LlmRequest) -> LlmResponse:
        try:
            response = self.__client.chat.completions.create(
                model=request.model,
                max_completion_tokens=request.max_output_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": request.schema_name,
                        "strict": True,
                        "schema": request.json_schema,
                    },
                },
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {
                        "role": "user",
                        "content": [
                            *_image_parts(request.images),
                            {"type": "text", "text": request.user_prompt},
                        ],
                    },
                ],
            )
        except _PERMANENT_ERRORS as error:
            raise LlmPermanentError(str(error)) from error

        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LlmRefusalError(f"Model refused the request: {choice.message.refusal}")

        usage = response.usage
        cached_tokens = _cached_tokens(usage)
        return LlmResponse(
            payload=_parse_payload(choice.message.content),
            model=response.model,
            input_tokens=(usage.prompt_tokens if usage else 0) - cached_tokens,
            output_tokens=usage.completion_tokens if usage else 0,
            cache_read_tokens=cached_tokens,
        )


def _image_parts(images: tuple[LlmImage, ...]) -> list[dict]:
    return [
        {"type": "image_url", "image_url": {"url": image.data_uri if image.base64_data else image.url}}
        for image in images
    ]


def _cached_tokens(usage) -> int:
    details = getattr(usage, "prompt_tokens_details", None) if usage else None
    return getattr(details, "cached_tokens", 0) or 0


def _parse_payload(content: Optional[str]) -> dict:
    if not content:
        raise LlmResponseFormatError("Response carries no content")
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise LlmResponseFormatError(f"Response is not valid JSON: {content[:500]}") from error
