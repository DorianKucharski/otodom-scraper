from __future__ import annotations

from pathlib import Path

from llm import prompts
from llm.prompts import PromptTemplate

SCREENING_TEMPLATE_NAME = "screening"
EVALUATION_TEMPLATE_NAME = "evaluation"

_PROMPTS_DIRECTORY = Path(__file__).parent / "prompts"


def load_prompt_template(name: str) -> PromptTemplate:
    return prompts.load_prompt_template(_PROMPTS_DIRECTORY, name)
