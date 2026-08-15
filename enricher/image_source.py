from __future__ import annotations

import base64
import logging
from typing import Optional

import cloudscraper

from data.models import Ad, AdImage
from .config import EnricherConfig
from .llm.client import LlmImage

logger = logging.getLogger(__name__)

_MEDIA_TYPE_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_DEFAULT_MEDIA_TYPE = "image/jpeg"
_DOWNLOAD_TIMEOUT_SECONDS = 30


class ImageSource:
    def __init__(self, config: EnricherConfig):
        self.__config = config
        self.__scraper = cloudscraper.create_scraper()

    def images_for(self, ad: Ad) -> tuple[LlmImage, ...]:
        selected = select_images(ad.images, self.__config.max_images)
        urls = (getattr(image, self.__config.image_variant) for image in selected)
        images = tuple(LlmImage(media_type=media_type_of(url), url=url) for url in urls if url)

        return self.downloaded(images) if self.__config.download_images else images

    def downloaded(self, images: tuple[LlmImage, ...]) -> tuple[LlmImage, ...]:
        fetched = (self.__download(image) for image in images)
        return tuple(image for image in fetched if image is not None)

    def __download(self, image: LlmImage) -> Optional[LlmImage]:
        if image.base64_data is not None:
            return image

        try:
            response = self.__scraper.get(image.url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
            if response.status_code != 200:
                logger.warning("Skipping image %s - status %s", image.url, response.status_code)
                return None
            return LlmImage(
                media_type=response.headers.get("content-type", image.media_type).split(";")[0],
                url=image.url,
                base64_data=base64.standard_b64encode(response.content).decode("ascii"),
            )
        except Exception as error:
            logger.warning("Skipping image %s - %s", image.url, error)
            return None


def select_images(images: list[AdImage], limit: int) -> list[AdImage]:
    ordered = sorted(images, key=lambda image: image.position)
    if limit <= 0 or len(ordered) <= limit:
        return ordered
    if limit == 1:
        return ordered[:1]

    step = (len(ordered) - 1) / (limit - 1)
    return [ordered[round(index * step)] for index in range(limit)]


def media_type_of(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    for extension, media_type in _MEDIA_TYPE_BY_EXTENSION.items():
        if path.endswith(extension):
            return media_type
    return _DEFAULT_MEDIA_TYPE
