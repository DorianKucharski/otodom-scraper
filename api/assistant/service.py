from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from data.models import AssistantCallKind
from llm.client import LlmRequest
from llm.prompts import load_prompt_template
from ..schemas import (
    AssistantCriterion, AssistantPlan, AssistantRankedAd, AssistantRankResponse, AssistantInterpretResponse,
    FacetsResponse,
)
from .calls import AssistantLlm
from .config import AssistantConfig
from .interpret import Criterion, SearchPlan, interpretation_schema, plan_from_payload, vocabulary
from .rank import load_candidates, ranked_from_payload, ranking_schema

_PROMPTS_DIRECTORY = Path(__file__).parent / "prompts"


class Assistant:
    def __init__(self, config: AssistantConfig, llm: AssistantLlm):
        self.__config = config
        self.__llm = llm
        self.__interpret_template = load_prompt_template(_PROMPTS_DIRECTORY, "interpret")
        self.__rank_template = load_prompt_template(_PROMPTS_DIRECTORY, "rank")

    @property
    def daily_budget_usd(self) -> float:
        return self.__config.daily_budget_usd

    def interpret(
            self,
            message: str,
            history: list[str],
            previous: Optional[AssistantPlan],
            facets: FacetsResponse,
            author: Optional[str],
    ) -> AssistantInterpretResponse:
        template = self.__interpret_template
        request = LlmRequest(
            model=self.__config.interpret_model,
            system_prompt=template.system_prompt,
            user_prompt=template.render_user_prompt({
                "today": date.today().isoformat(),
                "vocabulary": vocabulary(facets),
                "previous": _previous_text(previous),
                "history": history,
                "message": message,
            }),
            json_schema=interpretation_schema(facets),
            schema_name="search_plan",
            max_output_tokens=self.__config.max_output_tokens,
        )
        completion = self.__llm.complete(
            AssistantCallKind.INTERPRET, request, author, message,
            {"history": history, "previous": previous.model_dump(mode="json") if previous else None},
        )
        plan = plan_from_payload(completion.payload, facets)
        return AssistantInterpretResponse(plan=to_plan_response(plan), cost_usd=completion.cost_usd)

    def rank(
            self,
            session: Session,
            message: str,
            history: list[str],
            plan: AssistantPlan,
            author: Optional[str],
    ) -> AssistantRankResponse:
        search_plan = to_search_plan(plan)
        pool = load_candidates(session, search_plan, self.__config.candidates, self.__config.description_characters)
        if not pool.candidates:
            return AssistantRankResponse(
                overview="Żadne ogłoszenie nie spełnia ustawionych filtrów. Poluzuj warunki i spróbuj ponownie.",
                items=[], candidates_considered=0, total_matching=pool.total_matching, cost_usd=0,
            )

        template = self.__rank_template
        request = LlmRequest(
            model=self.__config.rank_model,
            system_prompt=template.system_prompt,
            user_prompt=template.render_user_prompt({
                "message": message,
                "history": history,
                "understood": search_plan.understood,
                "criteria": search_plan.criteria,
                "cards": [candidate.card for candidate in pool.candidates],
                "total_matching": pool.total_matching,
            }),
            json_schema=ranking_schema([candidate.card.id for candidate in pool.candidates]),
            schema_name="ranking",
            max_output_tokens=self.__config.max_output_tokens,
            effort=self.__config.rank_effort,
        )
        completion = self.__llm.complete(
            AssistantCallKind.RANK, request, author, message,
            {"plan": plan.model_dump(mode="json"), "candidate_ids": [c.card.id for c in pool.candidates]},
        )
        ranked = ranked_from_payload(completion.payload, pool.candidates)

        return AssistantRankResponse(
            overview=(completion.payload.get("overview") or "").strip(),
            items=[
                AssistantRankedAd(
                    ad=item.candidate.summary,
                    fit_score=item.fit_score,
                    headline=item.headline,
                    matches=list(item.matches),
                    gaps=list(item.gaps),
                    evaluated=item.candidate.evaluated,
                )
                for item in ranked
            ],
            candidates_considered=len(pool.candidates),
            total_matching=pool.total_matching,
            cost_usd=completion.cost_usd,
        )


def to_plan_response(plan: SearchPlan) -> AssistantPlan:
    return AssistantPlan(
        query=plan.query,
        keywords=list(plan.keywords),
        criteria=[AssistantCriterion(text=criterion.text, importance=criterion.importance) for criterion in plan.criteria],
        understood=plan.understood,
        sort=plan.sort,
        warnings=list(plan.warnings),
    )


def to_search_plan(plan: AssistantPlan) -> SearchPlan:
    return SearchPlan(
        query=plan.query,
        keywords=tuple(plan.keywords),
        criteria=tuple(Criterion(text=criterion.text, importance=criterion.importance) for criterion in plan.criteria),
        understood=plan.understood,
        sort=plan.sort,
    )


def _previous_text(previous: Optional[AssistantPlan]) -> Optional[str]:
    if previous is None:
        return None
    return json.dumps({
        "filters": previous.query.model_dump(mode="json", exclude_defaults=True, exclude={"limit", "offset"}),
        "keywords": previous.keywords,
        "criteria": [criterion.model_dump() for criterion in previous.criteria],
        "sort": previous.sort,
        "understood": previous.understood,
    }, ensure_ascii=False, indent=1)
