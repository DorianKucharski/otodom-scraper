from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.https import install_https_redirect

_PUBLIC_URL = "https://flats.example"


def _client(public_url) -> TestClient:
    app = FastAPI()
    install_https_redirect(app, public_url)

    @app.get("/api/ads")
    def ads() -> list:
        return []

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return TestClient(app, follow_redirects=False)


class TestHttpsRedirect(unittest.TestCase):

    def test_plain_http_is_sent_to_the_public_url_with_path_and_query(self):
        response = _client(_PUBLIC_URL).get("/api/ads?limit=5")

        self.assertEqual(308, response.status_code)
        self.assertEqual(f"{_PUBLIC_URL}/api/ads?limit=5", response.headers["location"])

    def test_a_request_the_proxy_received_over_https_is_served(self):
        response = _client(_PUBLIC_URL).get("/api/ads", headers={"X-Forwarded-Proto": "https"})

        self.assertEqual(200, response.status_code)

    def test_http_through_the_proxy_is_redirected_too(self):
        response = _client(_PUBLIC_URL).get("/api/ads", headers={"X-Forwarded-Proto": "http"})

        self.assertEqual(308, response.status_code)

    def test_the_health_check_stays_reachable_over_http(self):
        self.assertEqual(200, _client(_PUBLIC_URL).get("/api/health").status_code)

    def test_without_a_public_url_nothing_is_redirected(self):
        self.assertEqual(200, _client(None).get("/api/ads").status_code)

    def test_a_non_https_public_url_is_rejected(self):
        with self.assertRaises(ValueError):
            _client("http://flats.example")


if __name__ == "__main__":
    unittest.main()
