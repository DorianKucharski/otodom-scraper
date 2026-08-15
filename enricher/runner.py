from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session, selectinload

from data.models import Ad, AdEvaluation, AdScreening, EvaluationStatus, ScreeningStatus
from database import DatabaseManager
from .ad_context import AdContext, build_ad_context
from .config import EnricherConfig, cost_usd_for
from .fingerprint import content_fingerprint, has_price_drifted
from .image_fallback import complete_with_image_fallback
from .image_source import ImageSource
from .llm.client import LlmClient, LlmImage, LlmRequest, LlmResponse
from .market_context import MarketContext
from .prompt_templates import EVALUATION_TEMPLATE_NAME, PromptTemplate, SCREENING_TEMPLATE_NAME, load_prompt_template
from .results import EvaluationResult, ScreeningResult
from .retry import call_with_retry
from .schema import EVALUATION_SCHEMA, SCREENING_SCHEMA
from .selector import AdFilter, evaluation_candidate_ids, screening_candidate_ids

logger = logging.getLogger(__name__)

SKIPPED = "skipped"
FAILED = "failed"

_AD_RELATIONS = (
    "images",
    "features",
    "flat_equipment",
    "flat_areas",
    "flat_parking",
    "building_windows",
    "building_conveniences",
    "building_security",
    "city",
    "district",
    "province",
)


@dataclass(frozen=True)
class PreparedAd:
    ad_id: int
    ad_modified_at: datetime
    price_value: int
    fingerprint: str
    context: AdContext
    images: tuple[LlmImage, ...] = ()


@dataclass(frozen=True)
class AdOutcome:
    ad_id: int
    status: str
    result: Optional[Any] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class RunSummary:
    stage: str
    candidates: int
    processed: int
    skipped: int
    failed: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    outcomes: tuple[AdOutcome, ...]

    def log(self) -> None:
        logger.info(
            "%s finished: %s candidates, %s processed, %s skipped, %s failed, "
            "%s input tokens, %s output tokens, %.4f USD",
            self.stage, self.candidates, self.processed, self.skipped, self.failed,
            self.input_tokens, self.output_tokens, self.cost_usd,
        )


class EnrichmentRunner:
    def __init__(self, database_manager: DatabaseManager, llm_client: LlmClient, config: EnricherConfig):
        self.__database_manager = database_manager
        self.__llm_client = llm_client
        self.__config = config
        self.__image_source = ImageSource(config)
        self.__screening_template = load_prompt_template(SCREENING_TEMPLATE_NAME)
        self.__evaluation_template = load_prompt_template(EVALUATION_TEMPLATE_NAME)
        self.__images_must_be_downloaded = config.download_images

    @property
    def screening_prompt_version(self) -> str:
        return self.__screening_template.version

    @property
    def evaluation_prompt_version(self) -> str:
        return self.__evaluation_template.version

    def screen(self, ad_filter: AdFilter, force: bool = False, dry_run: bool = False) -> RunSummary:
        with self.__database_manager.get_session() as session:
            candidate_ids = screening_candidate_ids(
                session, ad_filter, self.__screening_template.version, force
            )

        logger.info("Screening %s ads with %s", len(candidate_ids), self.__config.screening_model)
        outcomes = self.__run_all(candidate_ids, lambda ad_id: self.__screen_ad(ad_id, force, dry_run))
        return _summarize("screening", len(candidate_ids), outcomes)

    def evaluate(self, ad_filter: AdFilter, force: bool = False, dry_run: bool = False) -> RunSummary:
        with self.__database_manager.get_session() as session:
            candidate_ids = evaluation_candidate_ids(
                session,
                ad_filter,
                self.__evaluation_template.version,
                self.__config.price_drift_threshold,
                force,
                require_passed_screening=not dry_run,
            )
            market_context = MarketContext.load(session)

        logger.info("Evaluating %s ads with %s", len(candidate_ids), self.__config.evaluation_model)
        outcomes = self.__run_all(
            candidate_ids, lambda ad_id: self.__evaluate_ad(ad_id, market_context, force, dry_run)
        )
        return _summarize("evaluation", len(candidate_ids), outcomes)

    def __run_all(self, ad_ids: list[int], action: Callable[[int], AdOutcome]) -> tuple[AdOutcome, ...]:
        if not ad_ids:
            return ()
        with ThreadPoolExecutor(max_workers=self.__config.concurrency) as executor:
            return tuple(executor.map(action, ad_ids))

    def __screen_ad(self, ad_id: int, force: bool, dry_run: bool) -> AdOutcome:
        template = self.__screening_template
        try:
            prepared = self.__prepare_screening(ad_id, force)
            if prepared is None:
                return AdOutcome(ad_id=ad_id, status=SKIPPED)

            response = self.__complete(
                model=self.__config.screening_model,
                effort=self.__config.screening_effort,
                template=template,
                context=prepared.context,
                json_schema=SCREENING_SCHEMA,
                schema_name="ad_screening",
                images=(),
                description=f"Screening ad {ad_id}",
            )
            result = ScreeningResult.from_payload(response.payload)

            if not dry_run:
                self.__save(_screening_row(prepared, result, response, template.version, self.__llm_client.provider))

            return _outcome_of(ad_id, result, response, result.status)
        except Exception as error:
            logger.error("Screening ad %s failed: %s", ad_id, error)
            if not dry_run:
                self.__record_failure(ad_id, AdScreening, ScreeningStatus.FAILED, template.version,
                                      self.__config.screening_model, error)
            return AdOutcome(ad_id=ad_id, status=FAILED, error=str(error))

    def __evaluate_ad(
            self,
            ad_id: int,
            market_context: MarketContext,
            force: bool,
            dry_run: bool,
    ) -> AdOutcome:
        template = self.__evaluation_template
        try:
            prepared = self.__prepare_evaluation(ad_id, market_context, force)
            if prepared is None:
                return AdOutcome(ad_id=ad_id, status=SKIPPED)

            response, images = self.__complete_evaluation(prepared, template)
            result = EvaluationResult.from_payload(response.payload)
            status = EvaluationStatus.OK if images else EvaluationStatus.NO_IMAGES
            prepared = replace(prepared, images=images)

            if not dry_run:
                self.__save(_evaluation_row(prepared, result, response, template.version,
                                            self.__llm_client.provider, status))

            return _outcome_of(ad_id, result, response, status.value)
        except Exception as error:
            logger.error("Evaluating ad %s failed: %s", ad_id, error)
            if not dry_run:
                self.__record_failure(ad_id, AdEvaluation, EvaluationStatus.FAILED, template.version,
                                      self.__config.evaluation_model, error)
            return AdOutcome(ad_id=ad_id, status=FAILED, error=str(error))

    def __complete_evaluation(
            self,
            prepared: PreparedAd,
            template: PromptTemplate,
    ) -> tuple[LlmResponse, tuple[LlmImage, ...]]:
        attempt = complete_with_image_fallback(
            evaluate=lambda images: self.__evaluate_once(prepared, template, images),
            download=self.__image_source.downloaded,
            images=prepared.images,
            images_must_be_downloaded=self.__images_must_be_downloaded,
        )

        if attempt.images_must_be_downloaded and not self.__images_must_be_downloaded:
            logger.warning(
                "The API could not reach the image URLs of ad %s, downloading images from now on. "
                "Set LLM_DOWNLOAD_IMAGES=true to skip this failing attempt after a restart.",
                prepared.ad_id,
            )
            self.__images_must_be_downloaded = True

        return attempt.response, attempt.images

    def __evaluate_once(
            self,
            prepared: PreparedAd,
            template: PromptTemplate,
            images: tuple[LlmImage, ...],
    ) -> LlmResponse:
        return self.__complete(
            model=self.__config.evaluation_model,
            effort=self.__config.evaluation_effort,
            template=template,
            context=replace(prepared.context, images_evaluated=len(images)),
            json_schema=EVALUATION_SCHEMA,
            schema_name="ad_evaluation",
            images=images,
            description=f"Evaluating ad {prepared.ad_id}",
        )

    def __prepare_screening(self, ad_id: int, force: bool) -> Optional[PreparedAd]:
        with self.__database_manager.get_session() as session:
            ad = _load_ad(session, ad_id)
            if ad is None:
                return None

            fingerprint = content_fingerprint(ad)
            existing = session.get(AdScreening, ad_id)
            if _is_up_to_date(existing, fingerprint, self.__screening_template.version, force):
                existing.ad_modified_at = ad.modified_at
                return None

            return _prepared_ad(ad, fingerprint, build_ad_context(ad))

    def __prepare_evaluation(
            self,
            ad_id: int,
            market_context: MarketContext,
            force: bool,
    ) -> Optional[PreparedAd]:
        with self.__database_manager.get_session() as session:
            ad = _load_ad(session, ad_id)
            if ad is None:
                return None

            fingerprint = content_fingerprint(ad)
            existing = session.get(AdEvaluation, ad_id)
            price_drifted = existing is not None and has_price_drifted(
                ad.price_value, existing.price_at_evaluation, self.__config.price_drift_threshold
            )
            if _is_up_to_date(existing, fingerprint, self.__evaluation_template.version, force) \
                    and not price_drifted:
                existing.ad_modified_at = ad.modified_at
                return None

            screening = session.get(AdScreening, ad_id)
            images = self.__image_source.images_for(ad)
            context = build_ad_context(
                ad,
                market_context=market_context,
                screening_attributes=screening.extracted_attributes if screening else None,
                images_evaluated=len(images),
            )
            return _prepared_ad(ad, fingerprint, context, images)

    def __complete(
            self,
            model: str,
            effort: Optional[str],
            template: PromptTemplate,
            context: AdContext,
            json_schema: dict,
            schema_name: str,
            images: tuple[LlmImage, ...],
            description: str,
    ) -> LlmResponse:
        request = LlmRequest(
            model=model,
            system_prompt=template.system_prompt,
            user_prompt=template.render_user_prompt({"ad": context}),
            json_schema=json_schema,
            schema_name=schema_name,
            max_output_tokens=self.__config.max_output_tokens,
            effort=effort,
            images=images,
        )
        return call_with_retry(
            lambda: self.__llm_client.complete(request),
            max_tries=self.__config.max_tries,
            pause_seconds=self.__config.retry_pause_seconds,
            description=description,
        )

    def __save(self, row) -> None:
        with self.__database_manager.get_session() as session:
            session.merge(row)

    def __record_failure(self, ad_id, enrichment_model, failed_status, prompt_version, model, error) -> None:
        try:
            with self.__database_manager.get_session() as session:
                existing = session.get(enrichment_model, ad_id)
                if existing is None:
                    session.add(enrichment_model(
                        ad_id=ad_id,
                        status=failed_status,
                        content_fingerprint="",
                        prompt_version=prompt_version,
                        provider=self.__llm_client.provider,
                        model=model,
                        attempts=1,
                        error_message=str(error)[:2000],
                    ))
                    return
                existing.status = failed_status
                existing.attempts = (existing.attempts or 0) + 1
                existing.error_message = str(error)[:2000]
        except Exception as write_error:
            logger.error("Could not record failure for ad %s: %s", ad_id, write_error)


def _load_ad(session: Session, ad_id: int) -> Optional[Ad]:
    return (
        session.query(Ad)
        .options(*(selectinload(getattr(Ad, relation)) for relation in _AD_RELATIONS))
        .filter(Ad.id == ad_id)
        .first()
    )


def _prepared_ad(ad: Ad, fingerprint: str, context: AdContext, images: tuple[LlmImage, ...] = ()) -> PreparedAd:
    return PreparedAd(
        ad_id=ad.id,
        ad_modified_at=ad.modified_at,
        price_value=ad.price_value,
        fingerprint=fingerprint,
        context=context,
        images=images,
    )


def _is_up_to_date(existing, fingerprint: str, prompt_version: str, force: bool) -> bool:
    return (
            not force
            and existing is not None
            and existing.content_fingerprint == fingerprint
            and existing.prompt_version == prompt_version
            and existing.status != FAILED
    )


def _screening_row(
        prepared: PreparedAd,
        result: ScreeningResult,
        response: LlmResponse,
        prompt_version: str,
        provider: str,
) -> AdScreening:
    return AdScreening(
        ad_id=prepared.ad_id,
        status=ScreeningStatus(result.status),
        rejection_reason=result.rejection_reason,
        extracted_attributes=dict(result.extracted_attributes),
        content_fingerprint=prepared.fingerprint,
        ad_modified_at=prepared.ad_modified_at,
        prompt_version=prompt_version,
        provider=provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=_cost_of(response),
        attempts=1,
        error_message=None,
    )


def _evaluation_row(
        prepared: PreparedAd,
        result: EvaluationResult,
        response: LlmResponse,
        prompt_version: str,
        provider: str,
        status: EvaluationStatus,
) -> AdEvaluation:
    return AdEvaluation(
        ad_id=prepared.ad_id,
        status=status,
        **dict(result.scores),
        renovation_needed=result.renovation_needed,
        style_tag=result.style_tag,
        summary=result.summary,
        strengths=list(result.strengths),
        concerns=list(result.concerns),
        attributes=dict(result.attributes),
        content_fingerprint=prepared.fingerprint,
        ad_modified_at=prepared.ad_modified_at,
        price_at_evaluation=prepared.price_value,
        images_evaluated=len(prepared.images),
        prompt_version=prompt_version,
        provider=provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=_cost_of(response),
        attempts=1,
        error_message=None,
    )


def _cost_of(response: LlmResponse) -> Optional[float]:
    return cost_usd_for(
        response.model,
        response.input_tokens,
        response.output_tokens,
        response.cache_read_tokens,
        response.cache_write_tokens,
    )


def _outcome_of(ad_id: int, result: Any, response: LlmResponse, status: str) -> AdOutcome:
    return AdOutcome(
        ad_id=ad_id,
        status=status,
        result=result,
        input_tokens=response.input_tokens + response.cache_read_tokens + response.cache_write_tokens,
        output_tokens=response.output_tokens,
        cost_usd=_cost_of(response) or 0.0,
    )


def _summarize(stage: str, candidates: int, outcomes: tuple[AdOutcome, ...]) -> RunSummary:
    return RunSummary(
        stage=stage,
        candidates=candidates,
        processed=sum(1 for outcome in outcomes if outcome.status not in (SKIPPED, FAILED)),
        skipped=sum(1 for outcome in outcomes if outcome.status == SKIPPED),
        failed=sum(1 for outcome in outcomes if outcome.status == FAILED),
        input_tokens=sum(outcome.input_tokens for outcome in outcomes),
        output_tokens=sum(outcome.output_tokens for outcome in outcomes),
        cost_usd=sum(outcome.cost_usd for outcome in outcomes),
        outcomes=outcomes,
    )
