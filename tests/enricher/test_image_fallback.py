from __future__ import annotations

import unittest

from enricher.image_fallback import complete_with_image_fallback, is_image_download_error
from enricher.llm.client import LlmImage, LlmPermanentError, LlmResponse

_UNREACHABLE_URL_ERROR = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Unable to download the file. Please verify the URL and try again.'}}"
)
_UNSUPPORTED_EFFORT_ERROR = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'This model does not support the effort parameter.'}}"
)

_URL_IMAGES = (
    LlmImage(media_type="image/jpeg", url="https://cdn/1.jpeg"),
    LlmImage(media_type="image/jpeg", url="https://cdn/2.jpeg"),
)


def _response() -> LlmResponse:
    return LlmResponse(payload={}, model="claude-sonnet-5", input_tokens=10, output_tokens=1)


class _Recorder:
    def __init__(self, failing_error: Exception | None = _UNREACHABLE_URL_ERROR):
        self.__failing_error = failing_error
        self.attempts: list[tuple[LlmImage, ...]] = []
        self.download_calls = 0

    def evaluate(self, images: tuple[LlmImage, ...]) -> LlmResponse:
        self.attempts.append(images)
        if self.__failing_error and any(image.base64_data is None for image in images):
            raise LlmPermanentError(self.__failing_error)
        return _response()

    def download(self, images: tuple[LlmImage, ...]) -> tuple[LlmImage, ...]:
        self.download_calls += 1
        return tuple(
            LlmImage(media_type=image.media_type, url=image.url, base64_data="ZmFrZQ==")
            for image in images
        )


class TestImageDownloadErrorDetection(unittest.TestCase):

    def test_unreachable_url_is_recognised(self):
        self.assertTrue(is_image_download_error(LlmPermanentError(_UNREACHABLE_URL_ERROR)))

    def test_unrelated_bad_request_is_not_recognised(self):
        self.assertFalse(is_image_download_error(LlmPermanentError(_UNSUPPORTED_EFFORT_ERROR)))

    def test_refusal_is_not_recognised(self):
        self.assertFalse(is_image_download_error(LlmPermanentError("Model refused the request: cyber")))


class TestCompleteWithImageFallback(unittest.TestCase):

    def test_reachable_urls_are_sent_as_is(self):
        recorder = _Recorder(failing_error=None)

        attempt = complete_with_image_fallback(
            recorder.evaluate, recorder.download, _URL_IMAGES, images_must_be_downloaded=False
        )

        self.assertEqual(1, len(recorder.attempts))
        self.assertEqual(0, recorder.download_calls)
        self.assertFalse(attempt.images_must_be_downloaded)

    def test_unreachable_urls_are_retried_as_downloads(self):
        recorder = _Recorder()

        attempt = complete_with_image_fallback(
            recorder.evaluate, recorder.download, _URL_IMAGES, images_must_be_downloaded=False
        )

        self.assertEqual(2, len(recorder.attempts))
        self.assertIsNone(recorder.attempts[0][0].base64_data)
        self.assertIsNotNone(recorder.attempts[1][0].base64_data)
        self.assertTrue(all(image.base64_data for image in attempt.images))

    def test_the_retry_is_remembered_for_the_next_ad(self):
        recorder = _Recorder()

        attempt = complete_with_image_fallback(
            recorder.evaluate, recorder.download, _URL_IMAGES, images_must_be_downloaded=False
        )

        self.assertTrue(attempt.images_must_be_downloaded)

    def test_a_remembered_retry_skips_the_failing_attempt(self):
        recorder = _Recorder()

        complete_with_image_fallback(
            recorder.evaluate, recorder.download, _URL_IMAGES, images_must_be_downloaded=True
        )

        self.assertEqual(1, len(recorder.attempts))
        self.assertIsNotNone(recorder.attempts[0][0].base64_data)

    def test_an_unrelated_bad_request_is_not_retried(self):
        recorder = _Recorder(failing_error=_UNSUPPORTED_EFFORT_ERROR)

        with self.assertRaises(LlmPermanentError):
            complete_with_image_fallback(
                recorder.evaluate, recorder.download, _URL_IMAGES, images_must_be_downloaded=False
            )

        self.assertEqual(1, len(recorder.attempts))
        self.assertEqual(0, recorder.download_calls)

    def test_ads_without_images_do_not_trigger_a_download(self):
        recorder = _Recorder()
        recorder.evaluate = lambda images: (_ for _ in ()).throw(LlmPermanentError(_UNREACHABLE_URL_ERROR))

        with self.assertRaises(LlmPermanentError):
            complete_with_image_fallback(
                recorder.evaluate, recorder.download, (), images_must_be_downloaded=False
            )

        self.assertEqual(0, recorder.download_calls)

    def test_a_download_failing_twice_gives_up(self):
        recorder = _Recorder()
        recorder.download = lambda images: images

        with self.assertRaises(LlmPermanentError):
            complete_with_image_fallback(
                recorder.evaluate, recorder.download, _URL_IMAGES, images_must_be_downloaded=False
            )

        self.assertEqual(2, len(recorder.attempts))


if __name__ == "__main__":
    unittest.main()
