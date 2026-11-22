from __future__ import annotations

from datetime import UTC, datetime, timedelta

from postoffice_api.security import TokenService
from tests.conftest import SECRET


def _error(res):
    body = res.get_json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]


def test_register_creates_account_in_lab_domain(client, users):
    res = client.post(
        "/api/auth/register",
        json={"name": "  Ana Torres ", "username": "Ana", "password": "password123"},
    )
    assert res.status_code == 201
    assert res.get_json() == {"user": {"email": "ana@postoffice.test", "name": "Ana Torres"}}
    stored = users.get("ana@postoffice.test")
    assert stored.password_hash.startswith("{BLF-CRYPT}$2b$")
    assert "password123" not in stored.password_hash


def test_register_duplicate_address_is_conflict(client, register):
    register("ana")
    res = client.post(
        "/api/auth/register", json={"name": "Otra", "username": "ana", "password": "password123"}
    )
    assert res.status_code == 409
    assert _error(res)["code"] == "email_taken"


def test_register_validation_lists_every_field(client):
    res = client.post(
        "/api/auth/register", json={"name": "A", "username": "no spaces!", "password": "short"}
    )
    assert res.status_code == 422
    error = _error(res)
    assert error["code"] == "validation_error"
    assert {d["field"] for d in error["details"]} == {"name", "username", "password"}


def test_register_rejects_unknown_fields_and_non_json(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Ana", "username": "ana", "password": "password123", "admin": True},
    )
    assert res.status_code == 422
    res = client.post("/api/auth/register", data="nope", content_type="text/plain")
    assert res.status_code == 400
    assert _error(res)["code"] == "invalid_json"


def test_register_rejects_passwords_longer_than_bcrypt_limit(client):
    res = client.post(
        "/api/auth/register", json={"name": "Ana", "username": "ana", "password": "ñ" * 40}
    )
    assert res.status_code == 422


def test_login_accepts_local_part_or_full_address(client, register):
    register("ana", password="password123")
    for email in ("ana", "ANA@postoffice.test"):
        res = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["user"]["email"] == "ana@postoffice.test"
        assert TokenService(SECRET, 5).verify(body["token"]) == "ana@postoffice.test"


def test_login_with_wrong_password_or_unknown_user_is_401(client, register):
    register("ana")
    for payload in (
        {"email": "ana", "password": "wrong-password"},
        {"email": "ghost", "password": "password123"},
    ):
        res = client.post("/api/auth/login", json=payload)
        assert res.status_code == 401
        assert _error(res)["code"] == "invalid_credentials"


def test_token_never_contains_the_password(client, register):
    import jwt

    headers = register("ana", password="password123")
    token = headers["Authorization"].split()[1]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert set(claims) == {"sub", "iat", "exp"}


def test_me_requires_a_valid_bearer_token(client, register):
    headers = register("ana", name="Ana Torres")
    assert client.get("/api/auth/me", headers=headers).get_json() == {
        "user": {"email": "ana@postoffice.test", "name": "Ana Torres"}
    }
    assert client.get("/api/auth/me").status_code == 401
    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    assert _error(bad)["message"] == "Invalid session token"


def test_expired_token_is_rejected(client, register):
    register("ana")
    old = datetime.now(UTC) - timedelta(days=1)
    token = TokenService(SECRET, 5).issue("ana@postoffice.test", now=old)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert _error(res)["message"] == "Session expired"


def test_token_for_deleted_account_is_rejected(client, register, users):
    headers = register("ana")
    users.users.clear()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_health_and_unknown_route_use_json(client):
    assert client.get("/api/health").get_json()["status"] == "ok"
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert _error(res)["code"] == "not_found"
