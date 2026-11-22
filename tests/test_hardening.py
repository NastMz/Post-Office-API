"""Regression tests for the security review findings."""

from __future__ import annotations

import pytest

from postoffice_api.app import create_app
from postoffice_api.config import Settings
from postoffice_api.ratelimit import TrustedProxies, limiter
from postoffice_api.security import PasswordHasher
from postoffice_api.services import AuthService

DEV_JWT = "dev-only-secret-change-me-in-production"


def _env(monkeypatch, **values):
    for key in ("APP_ENV", "JWT_SECRET", "MAIL_MASTER_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


# -- 1. public development secrets -------------------------------------------
def test_development_secrets_are_refused_outside_development(monkeypatch):
    _env(monkeypatch, JWT_SECRET=DEV_JWT, MAIL_MASTER_PASSWORD="a-real-master-password")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings.from_env()
    _env(monkeypatch, JWT_SECRET="x" * 40, MAIL_MASTER_PASSWORD="master-dev")
    with pytest.raises(RuntimeError, match="MAIL_MASTER_PASSWORD"):
        Settings.from_env()


def test_development_secrets_are_accepted_with_explicit_dev_flag(monkeypatch):
    _env(monkeypatch, JWT_SECRET=DEV_JWT, MAIL_MASTER_PASSWORD="master-dev", APP_ENV="development")
    assert Settings.from_env().is_development


def test_real_secrets_start_in_production(monkeypatch):
    _env(monkeypatch, JWT_SECRET="r" * 48, MAIL_MASTER_PASSWORD="s3cr3t-master")
    settings = Settings.from_env()
    assert settings.app_env == "production"


# -- 3. header injection through CR/LF -----------------------------------------
@pytest.mark.parametrize("name", ["Ana\r\nBcc: victim@postoffice.test", "Ana\x00", "Ana\tTorres"])
def test_registration_rejects_control_characters_in_name(client, users, name):
    res = client.post(
        "/api/auth/register", json={"name": name, "username": "ana", "password": "password123"}
    )
    assert res.status_code == 422
    assert res.get_json()["error"]["details"][0]["field"] == "name"
    assert users.users == {}


@pytest.mark.parametrize("url", ["/api/messages", "/api/drafts"])
def test_subject_with_line_breaks_is_rejected(client, register, transport, url):
    headers = register("ana")
    register("bruno")
    res = client.post(
        url,
        json={"to": ["bruno"], "subject": "Hola\r\nBcc: x@postoffice.test", "body": "x"},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.get_json()["error"]["details"][0]["field"] == "subject"
    assert transport.sent == []


def test_body_keeps_newlines_and_tabs_but_rejects_nul(client, register):
    headers = register("ana")
    register("bruno")
    ok = client.post(
        "/api/messages", json={"to": ["bruno"], "body": "a\r\n\tb", "subject": "s"}, headers=headers
    )
    assert ok.status_code == 201
    bad = client.post(
        "/api/messages", json={"to": ["bruno"], "body": "a\x00b", "subject": "s"}, headers=headers
    )
    assert bad.status_code == 422


# -- 4. request size -------------------------------------------------------------
def test_oversized_body_is_413_not_500(client):
    huge = '{"email": "ana", "password": "' + "x" * (30 * 1024 * 1024) + '"}'
    res = client.post("/api/auth/login", data=huge, content_type="application/json")
    assert res.status_code == 413
    assert res.get_json()["error"]["code"] == "request_entity_too_large"


def test_overlong_addresses_are_422(client, register):
    long_address = "a" * 300 + "@postoffice.test"
    res = client.post("/api/auth/login", json={"email": long_address, "password": "x"})
    assert res.status_code == 422
    headers = register("ana")
    res = client.post(
        "/api/messages", json={"to": [long_address], "subject": "s", "body": "b"}, headers=headers
    )
    assert res.status_code == 422


# -- 5. rate limiting ------------------------------------------------------------
@pytest.fixture
def limited_client(settings, services):
    strict = Settings(**{**settings.__dict__, "auth_rate_limit": "3 per minute"})
    app = create_app(strict, services)
    limiter.reset()
    return app.test_client()


def test_login_is_rate_limited_per_client(limited_client):
    body = {"email": "ana", "password": "wrong-password"}
    codes = [limited_client.post("/api/auth/login", json=body).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]
    res = limited_client.post("/api/auth/login", json=body)
    assert res.get_json()["error"]["code"] == "too_many_requests"
    other = limited_client.post(
        "/api/auth/login", json=body, environ_base={"REMOTE_ADDR": "10.9.9.9"}
    )
    assert other.status_code == 401


def test_register_is_rate_limited(limited_client):
    codes = [
        limited_client.post(
            "/api/auth/register", json={"name": "Ana", "username": f"u{i}", "password": "password1"}
        ).status_code
        for i in range(4)
    ]
    assert codes == [201, 201, 201, 429]


def test_forwarded_for_is_ignored_unless_sent_by_a_trusted_proxy(limited_client):
    body = {"email": "ana", "password": "wrong-password"}
    for i in range(3):
        limited_client.post(
            "/api/auth/login", json=body, headers={"X-Forwarded-For": f"198.51.100.{i}"}
        )
    spoofed = limited_client.post(
        "/api/auth/login", json=body, headers={"X-Forwarded-For": "203.0.113.7"}
    )
    assert spoofed.status_code == 429


def test_trusted_proxies_resolve_literal_addresses():
    proxies = TrustedProxies(("127.0.0.1",))
    assert proxies.contains("127.0.0.1")
    assert not proxies.contains("10.0.0.1")
    assert not TrustedProxies(()).contains("127.0.0.1")


# -- timing and reserved names ---------------------------------------------------
def test_unknown_users_still_run_a_bcrypt_check(users, settings):
    calls = []

    class CountingHasher(PasswordHasher):
        def verify(self, password, stored):
            calls.append(stored)
            return super().verify(password, stored)

    from postoffice_api.security import TokenService

    auth = AuthService(
        users, CountingHasher(rounds=4), TokenService(settings.jwt_secret, 5), "x.test"
    )
    with pytest.raises(Exception, match="Wrong address"):
        auth.login("ghost", "whatever")
    assert len(calls) == 1 and calls[0].startswith("{BLF-CRYPT}$2b$")


@pytest.mark.parametrize("username", ["postmaster", "Abuse", "mailer-daemon", "api", "root"])
def test_reserved_local_parts_cannot_be_registered(client, username):
    res = client.post(
        "/api/auth/register", json={"name": "Nombre", "username": username, "password": "password1"}
    )
    assert res.status_code == 422
    assert res.get_json()["error"]["details"][0]["message"] == "this address is reserved"
