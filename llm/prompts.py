from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    system_prompt: str
    version: str
    _user_template: Template

    def render_user_prompt(self, context: dict) -> str:
        return self._user_template.render(**context)


def load_prompt_template(directory: Path, name: str) -> PromptTemplate:
    environment = Environment(
        loader=FileSystemLoader(directory),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    system_prompt = (directory / f"{name}_system.md").read_text(encoding="utf-8")
    user_template_source = (directory / f"{name}_user.jinja2").read_text(encoding="utf-8")

    return PromptTemplate(
        name=name,
        system_prompt=system_prompt,
        version=_version_of(system_prompt, user_template_source),
        _user_template=environment.get_template(f"{name}_user.jinja2"),
    )


def _version_of(system_prompt: str, user_template_source: str) -> str:
    digest = hashlib.sha256()
    digest.update(system_prompt.encode("utf-8"))
    digest.update(user_template_source.encode("utf-8"))
    return digest.hexdigest()[:12]
