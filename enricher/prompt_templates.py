from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template

SCREENING_TEMPLATE_NAME = "screening"
EVALUATION_TEMPLATE_NAME = "evaluation"

_PROMPTS_DIRECTORY = Path(__file__).parent / "prompts"

_ENVIRONMENT = Environment(
    loader=FileSystemLoader(_PROMPTS_DIRECTORY),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system_prompt: str
    version: str
    _user_template: Template

    def render_user_prompt(self, context: dict) -> str:
        return self._user_template.render(**context)


def load_prompt_template(name: str) -> PromptTemplate:
    system_prompt = (_PROMPTS_DIRECTORY / f"{name}_system.md").read_text(encoding="utf-8")
    user_template_source = (_PROMPTS_DIRECTORY / f"{name}_user.jinja2").read_text(encoding="utf-8")

    return PromptTemplate(
        name=name,
        system_prompt=system_prompt,
        version=_version_of(system_prompt, user_template_source),
        _user_template=_ENVIRONMENT.get_template(f"{name}_user.jinja2"),
    )


def _version_of(system_prompt: str, user_template_source: str) -> str:
    digest = hashlib.sha256()
    digest.update(system_prompt.encode("utf-8"))
    digest.update(user_template_source.encode("utf-8"))
    return digest.hexdigest()[:12]
