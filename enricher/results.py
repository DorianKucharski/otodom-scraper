from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .schema import SCORE_FIELD_NAMES


@dataclass(frozen=True)
class ScreeningResult:
    status: str
    rejection_reason: Optional[str]
    extracted_attributes: Mapping[str, str]

    @property
    def is_passed(self) -> bool:
        return self.status == "passed"

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "extracted_attributes": dict(self.extracted_attributes),
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "ScreeningResult":
        reason = (payload.get("rejection_reason") or "").strip()
        return cls(
            status=payload["status"],
            rejection_reason=reason or None,
            extracted_attributes=_attributes_to_mapping(payload.get("extracted_attributes")),
        )


@dataclass(frozen=True)
class EvaluationResult:
    scores: Mapping[str, int]
    renovation_needed: str
    style_tag: str
    summary: str
    strengths: tuple[str, ...]
    concerns: tuple[str, ...]
    attributes: Mapping[str, str]

    @property
    def overall_score(self) -> int:
        return self.scores["overall_score"]

    def as_dict(self) -> dict:
        return {
            **dict(self.scores),
            "renovation_needed": self.renovation_needed,
            "style_tag": self.style_tag,
            "summary": self.summary,
            "strengths": list(self.strengths),
            "concerns": list(self.concerns),
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "EvaluationResult":
        missing_scores = [name for name in SCORE_FIELD_NAMES if name not in payload]
        if missing_scores:
            raise ValueError(f"Evaluation payload is missing scores: {', '.join(missing_scores)}")

        return cls(
            scores=MappingProxyType({name: int(payload[name]) for name in SCORE_FIELD_NAMES}),
            renovation_needed=payload["renovation_needed"],
            style_tag=payload["style_tag"],
            summary=payload["summary"].strip(),
            strengths=tuple(payload.get("strengths") or ()),
            concerns=tuple(payload.get("concerns") or ()),
            attributes=_attributes_to_mapping(payload.get("attributes")),
        )


def _attributes_to_mapping(items: Optional[list[dict[str, Any]]]) -> Mapping[str, str]:
    if not items:
        return MappingProxyType({})
    return MappingProxyType({
        str(item["key"]).strip(): str(item["value"]).strip()
        for item in items
        if item.get("key") and item.get("value") is not None
    })
