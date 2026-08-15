from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import patch

import anthropic
import httpx

from enricher.llm.anthropic_client import AnthropicLlmClient
from enricher.llm.client import LlmImage, LlmPermanentError, LlmRefusalError, LlmRequest, LlmResponseFormatError
from enricher.retry import call_with_retry


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _Usage:
    input_tokens: int = 1000
    output_tokens: int = 200
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class _FakeMessage:
    content: list
    model: str = "claude-sonnet-5"
    stop_reason: str = "end_turn"
    stop_details: Optional[str] = None
    usage: _Usage = field(default_factory=_Usage)


class _RecordingMessages:
    def __init__(self, response: _FakeMessage):
        self.__response = response
        self.captured: dict[str, Any] = {}

    def create(self, **kwargs):
        self.captured = kwargs
        return self.__response


class _FakeAnthropic:
    def __init__(self, response: _FakeMessage):
        self.messages = _RecordingMessages(response)

    def __call__(self, **_kwargs):
        return self


def _request(images: tuple[LlmImage, ...] = (), effort: str | None = "medium") -> LlmRequest:
    return LlmRequest(
        model="claude-sonnet-5",
        system_prompt="Jesteś rzeczoznawcą.",
        user_prompt="Oceń to ogłoszenie.",
        json_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        schema_name="ad_evaluation",
        max_output_tokens=8000,
        effort=effort,
        images=images,
    )


def _client_for(response: _FakeMessage) -> tuple[AnthropicLlmClient, _RecordingMessages]:
    fake = _FakeAnthropic(response)
    with patch("enricher.llm.anthropic_client.anthropic.Anthropic", return_value=fake):
        client = AnthropicLlmClient(api_key="sk-ant-test")
    return client, fake.messages


class TestAnthropicRequestShape(unittest.TestCase):

    def setUp(self):
        self.client, self.messages = _client_for(_FakeMessage(content=[_TextBlock(text='{"overall_score": 7}')]))

    def test_schema_is_sent_as_structured_output(self):
        self.client.complete(_request())

        output_config = self.messages.captured["output_config"]
        self.assertEqual("json_schema", output_config["format"]["type"])
        self.assertEqual("medium", output_config["effort"])

    def test_effort_is_omitted_for_models_that_reject_it(self):
        self.client.complete(_request(effort=None))

        self.assertNotIn("effort", self.messages.captured["output_config"])

    def test_system_prompt_is_cached(self):
        self.client.complete(_request())

        system_block = self.messages.captured["system"][0]
        self.assertEqual("Jesteś rzeczoznawcą.", system_block["text"])
        self.assertEqual({"type": "ephemeral"}, system_block["cache_control"])

    def test_images_precede_the_text_block(self):
        images = (LlmImage(media_type="image/jpeg", url="https://cdn/1.jpeg"),)

        self.client.complete(_request(images))

        content = self.messages.captured["messages"][0]["content"]
        self.assertEqual("image", content[0]["type"])
        self.assertEqual({"type": "url", "url": "https://cdn/1.jpeg"}, content[0]["source"])
        self.assertEqual("text", content[-1]["type"])

    def test_downloaded_images_are_sent_as_base64(self):
        images = (LlmImage(media_type="image/png", url="https://cdn/1.png", base64_data="ZmFrZQ=="),)

        self.client.complete(_request(images))

        source = self.messages.captured["messages"][0]["content"][0]["source"]
        self.assertEqual("base64", source["type"])
        self.assertEqual("image/png", source["media_type"])
        self.assertEqual("ZmFrZQ==", source["data"])

    def test_no_images_leaves_only_the_text_block(self):
        self.client.complete(_request())

        self.assertEqual(1, len(self.messages.captured["messages"][0]["content"]))


class TestAnthropicResponseHandling(unittest.TestCase):

    def test_json_payload_is_parsed(self):
        client, _ = _client_for(_FakeMessage(content=[_TextBlock(text=json.dumps({"overall_score": 7}))]))

        response = client.complete(_request())

        self.assertEqual({"overall_score": 7}, response.payload)

    def test_usage_is_carried_over(self):
        usage = _Usage(input_tokens=9000, output_tokens=400, cache_read_input_tokens=1200,
                       cache_creation_input_tokens=800)
        client, _ = _client_for(_FakeMessage(content=[_TextBlock(text="{}")], usage=usage))

        response = client.complete(_request())

        self.assertEqual(9000, response.input_tokens)
        self.assertEqual(400, response.output_tokens)
        self.assertEqual(1200, response.cache_read_tokens)
        self.assertEqual(800, response.cache_write_tokens)

    def test_refusal_raises(self):
        client, _ = _client_for(_FakeMessage(content=[], stop_reason="refusal", stop_details="cyber"))

        with self.assertRaises(LlmRefusalError):
            client.complete(_request())

    def test_response_without_a_text_block_raises(self):
        client, _ = _client_for(_FakeMessage(content=[]))

        with self.assertRaises(LlmResponseFormatError):
            client.complete(_request())

    def test_invalid_json_raises(self):
        client, _ = _client_for(_FakeMessage(content=[_TextBlock(text="to nie jest json")]))

        with self.assertRaises(LlmResponseFormatError):
            client.complete(_request())


class TestPermanentErrors(unittest.TestCase):

    def __client_raising(self, error: Exception) -> AnthropicLlmClient:
        fake = _FakeAnthropic(_FakeMessage(content=[]))

        def raising(**_kwargs):
            raise error

        fake.messages.create = raising
        with patch("enricher.llm.anthropic_client.anthropic.Anthropic", return_value=fake):
            return AnthropicLlmClient(api_key="sk-ant-test")

    def __bad_request(self) -> anthropic.BadRequestError:
        response = httpx.Response(
            status_code=400,
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
            json={"type": "error", "error": {"type": "invalid_request_error",
                                             "message": "This model does not support the effort parameter."}},
        )
        return anthropic.BadRequestError("bad request", response=response, body=None)

    def test_bad_request_is_permanent(self):
        client = self.__client_raising(self.__bad_request())

        with self.assertRaises(LlmPermanentError):
            client.complete(_request())

    def test_a_permanent_error_is_not_retried(self):
        client = self.__client_raising(self.__bad_request())
        attempts = []

        def counted():
            attempts.append(1)
            return client.complete(_request())

        with self.assertRaises(LlmPermanentError):
            call_with_retry(counted, max_tries=3, pause_seconds=0, description="test")

        self.assertEqual(1, len(attempts))

    def test_a_transient_error_is_retried(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("connection reset")
            return "ok"

        self.assertEqual("ok", call_with_retry(flaky, max_tries=3, pause_seconds=0, description="test"))
        self.assertEqual(3, len(attempts))


if __name__ == "__main__":
    unittest.main()
