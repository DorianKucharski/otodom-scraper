from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .llm.client import LlmImage, LlmPermanentError, LlmResponse

Images = tuple[LlmImage, ...]


@dataclass(frozen=True)
class EvaluationAttempt:
    response: LlmResponse
    images: Images
    images_must_be_downloaded: bool


def is_image_download_error(error: LlmPermanentError) -> bool:
    return "download" in str(error).lower()


def complete_with_image_fallback(
        evaluate: Callable[[Images], LlmResponse],
        download: Callable[[Images], Images],
        images: Images,
        images_must_be_downloaded: bool,
) -> EvaluationAttempt:
    sent = download(images) if images_must_be_downloaded and images else images

    try:
        return EvaluationAttempt(evaluate(sent), sent, images_must_be_downloaded)
    except LlmPermanentError as error:
        if not images or images_must_be_downloaded or not is_image_download_error(error):
            raise

    downloaded = download(images)
    return EvaluationAttempt(evaluate(downloaded), downloaded, True)
