from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import SESSION_COOKIE, SESSION_LIFETIME, AuthSettings, install_auth, issue_session, read_session
from api.routers import auth

_SETTINGS = AuthSettings(password="tajne")
_NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _client(settings: AuthSettings) -> TestClient:
    app = FastAPI()
    install_auth(app, settings)
    app.include_router(auth.router)

    @app.get("/api/ads")
    def ads() -> list:
        return []

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/index.html")
    def frontend() -> dict:
        return {}

    return TestClient(app)


class TestSessionToken(unittest.TestCase):

    def test_an_issued_session_reads_back_the_name(self):
        token = issue_session("Żona", _SETTINGS, _NOW)

        self.assertEqual("Żona", read_session(token, _SETTINGS, _NOW + timedelta(days=30)))

    def test_a_tampered_session_is_rejected(self):
        payload, signature = issue_session("Dorian", _SETTINGS, _NOW).split(".")
        forged_payload = issue_session("Ktoś", _SETTINGS, _NOW).split(".")[0]

        self.assertIsNone(read_session(f"{forged_payload}.{signature}", _SETTINGS, _NOW))
        self.assertIsNone(read_session(f"{payload}.{signature[:-1]}0", _SETTINGS, _NOW))

    def test_changing_the_password_signs_everyone_out(self):
        token = issue_session("Dorian", _SETTINGS, _NOW)

        self.assertIsNone(read_session(token, AuthSettings(password="nowe"), _NOW))

    def test_an_expired_session_is_rejected(self):
        token = issue_session("Dorian", _SETTINGS, _NOW)

        self.assertIsNone(read_session(token, _SETTINGS, _NOW + SESSION_LIFETIME + timedelta(seconds=1)))

    def test_garbage_is_not_a_session(self):
        for token in (None, "", "abc", "abc.def", "...."):
            self.assertIsNone(read_session(token, _SETTINGS, _NOW))


class TestAuthMiddleware(unittest.TestCase):

    def test_the_api_requires_a_session(self):
        self.assertEqual(401, _client(_SETTINGS).get("/api/ads").status_code)

    def test_health_and_frontend_stay_public(self):
        client = _client(_SETTINGS)

        self.assertEqual(200, client.get("/api/health").status_code)
        self.assertEqual(200, client.get("/index.html").status_code)

    def test_docs_require_a_session(self):
        self.assertEqual(401, _client(_SETTINGS).get("/openapi.json").status_code)

    def test_a_wrong_password_does_not_log_in(self):
        auth._FAILED_LOGIN_DELAY_SECONDS = 0
        client = _client(_SETTINGS)

        response = client.post("/api/auth/login", json={"name": "Dorian", "password": "zle"})

        self.assertEqual(401, response.status_code)
        self.assertNotIn(SESSION_COOKIE, response.cookies)

    def test_logging_in_opens_the_api_and_remembers_the_name(self):
        client = _client(_SETTINGS)

        client.post("/api/auth/login", json={"name": " Dorian ", "password": "tajne"})

        self.assertEqual(200, client.get("/api/ads").status_code)
        self.assertEqual({"name": "Dorian", "auth_enabled": True}, client.get("/api/auth/me").json())

    def test_logging_out_closes_the_api(self):
        client = _client(_SETTINGS)
        client.post("/api/auth/login", json={"name": "Dorian", "password": "tajne"})

        client.post("/api/auth/logout")

        self.assertEqual(401, client.get("/api/ads").status_code)

    def test_without_a_password_the_api_is_open(self):
        client = _client(AuthSettings(password=None))

        self.assertEqual(200, client.get("/api/ads").status_code)
        self.assertEqual({"name": None, "auth_enabled": False}, client.get("/api/auth/me").json())


if __name__ == "__main__":
    unittest.main()
