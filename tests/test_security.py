from __future__ import annotations

import pytest

from postoffice_api.config import Settings
from postoffice_api.errors import ApiError
from postoffice_api.schemas import normalize_address
from postoffice_api.security import PasswordHasher, TokenService


def test_password_hash_is_dovecot_blf_crypt_and_salted():
    hasher = PasswordHasher(rounds=4)
    first, second = hasher.hash("secreto123"), hasher.hash("secreto123")
    assert first.startswith("{BLF-CRYPT}$2b$04$")
    assert first != second
    assert hasher.verify("secreto123", first)
    assert not hasher.verify("otro", first)


def test_verify_rejects_unknown_schemes_and_garbage():
    hasher = PasswordHasher(rounds=4)
    assert not hasher.verify("x", "{SHA512}abc")
    assert not hasher.verify("x", "{BLF-CRYPT}not-a-hash")


def test_token_service_requires_a_strong_secret():
    with pytest.raises(ValueError):
        TokenService("short", 10)


def test_token_signed_with_other_secret_is_rejected():
    token = TokenService("another-secret-that-is-long-enough-x", 10).issue("ana@postoffice.test")
    with pytest.raises(ApiError) as err:
        TokenService("the-real-secret-that-is-long-enough-x", 10).verify(token)
    assert err.value.status == 401


@pytest.mark.parametrize(
    ("value", "expected"),
    [("ana", "ana@postoffice.test"), ("ana.t@postoffice.test", "ana.t@postoffice.test")],
)
def test_normalize_address(value, expected):
    assert normalize_address(value, "postoffice.test", "to.0") == expected


@pytest.mark.parametrize(
    ("value", "code"),
    [("bad address", "validation_error"), ("x@gmail.com", "external_recipient")],
)
def test_normalize_address_errors(value, code):
    with pytest.raises(ApiError) as err:
        normalize_address(value, "postoffice.test", "to.0")
    assert err.value.code == code
    assert err.value.details[0]["field"] == "to.0"


def test_settings_from_env_requires_secrets(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings.from_env()
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("MAIL_MASTER_PASSWORD", "m")
    monkeypatch.setenv("CORS_ORIGINS", "http://a, http://b")
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    settings = Settings.from_env()
    assert settings.cors_origins == ("http://a", "http://b")
    assert settings.seed_demo_data is True
