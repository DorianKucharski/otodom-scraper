from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import patch

from enricher.llm.client import LlmImage, LlmRefusalError, LlmRequest, LlmResponseFormatError
from enricher.llm.openai_client import OpenAiLlmClient


@dataclass
class _Message:
    content: Optional[str]
    refusal: Optional[str] = None


@dataclass
class _Choice:
    message: _Message


@dataclass
class _PromptTokensDetails:
    cached_tokens: int = 0


@dataclass
class _Usage:
    prompt_tokens: int = 1000
    completion_tokens: int = 200
    prompt_tokens_details: _PromptTokensDetails = field(default_factory=_PromptTokensDetails)


@dataclass
class _FakeCompletion:
    choices: list
    model: str = "gpt-test"
    usage: _Usage = field(default_factory=_Usage)


class _RecordingCompletions:
    def __init__(self, response: _FakeCompletion):
        self.__response = response
        self.captured: dict[str, Any] = {}

    def create(self, **kwargs):
        self.captured = kwargs
        return self.__response


class _FakeOpenAi:
    def __init__(self, response: _FakeCompletion):
        self.chat = type("Chat", (), {"completions": _RecordingCompletions(response)})()


def _request(images: tuple[LlmImage, ...] = ()) -> LlmRequest:
    return LlmRequest(
        model="gpt-test",
        system_prompt="Jesteś rzeczoznawcą.",
        user_prompt="Oceń to ogłoszenie.",
        json_schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        schema_name="ad_evaluation",
        max_output_tokens=8000,
        effort="medium",
        images=images,
    )


def _client_for(response: _FakeCompletion) -> tuple[OpenAiLlmClient, _RecordingCompletions]:
    fake = _FakeOpenAi(response)
    with patch("enricher.llm.openai_client.OpenAI", return_value=fake):
        client = OpenAiLlmClient(api_key="sk-test")
    return client, fake.chat.completions


class TestOpenAiClient(unittest.TestCase):

    def test_schema_is_sent_in_strict_mode(self):
        client, completions = _client_for(_FakeCompletion(choices=[_Choice(_Message(content="{}"))]))

        client.complete(_request())

        response_format = completions.captured["response_format"]
        self.assertEqual("json_schema", response_format["type"])
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual("ad_evaluation", response_format["json_schema"]["name"])

    def test_system_prompt_is_the_first_message(self):
        client, completions = _client_for(_FakeCompletion(choices=[_Choice(_Message(content="{}"))]))

        client.complete(_request())

        self.assertEqual("system", completions.captured["messages"][0]["role"])

    def test_images_are_sent_as_image_url_parts(self):
        client, completions = _client_for(_FakeCompletion(choices=[_Choice(_Message(content="{}"))]))

        client.complete(_request((LlmImage(media_type="image/jpeg", url="https://cdn/1.jpeg"),)))

        part = completions.captured["messages"][1]["content"][0]
        self.assertEqual("image_url", part["type"])
        self.assertEqual("https://cdn/1.jpeg", part["image_url"]["url"])

    def test_downloaded_images_become_data_uris(self):
        client, completions = _client_for(_FakeCompletion(choices=[_Choice(_Message(content="{}"))]))

        client.complete(_request((LlmImage(media_type="image/png", url="https://cdn/1.png", base64_data="ZmFrZQ=="),)))

        part = completions.captured["messages"][1]["content"][0]
        self.assertEqual("data:image/png;base64,ZmFrZQ==", part["image_url"]["url"])

    def test_cached_tokens_are_reported_separately(self):
        usage = _Usage(prompt_tokens=5000, completion_tokens=300,
                       prompt_tokens_details=_PromptTokensDetails(cached_tokens=2000))
        client, _ = _client_for(_FakeCompletion(choices=[_Choice(_Message(content="{}"))], usage=usage))

        response = client.complete(_request())

        self.assertEqual(3000, response.input_tokens)
        self.assertEqual(2000, response.cache_read_tokens)

    def test_refusal_raises(self):
        client, _ = _client_for(_FakeCompletion(choices=[_Choice(_Message(content=None, refusal="nie mogę"))]))

        with self.assertRaises(LlmRefusalError):
            client.complete(_request())

    def test_invalid_json_raises(self):
        client, _ = _client_for(_FakeCompletion(choices=[_Choice(_Message(content="to nie jest json"))]))

        with self.assertRaises(LlmResponseFormatError):
            client.complete(_request())


if __name__ == "__main__":
    unittest.main()
