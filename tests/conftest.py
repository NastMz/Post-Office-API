from __future__ import annotations

import pytest

from postoffice_api.app import build_services, create_app
from postoffice_api.config import Settings
from postoffice_api.security import PasswordHasher
from tests.fakes import FakeStoreFactory, FakeTransport, FakeUserRepository

DOMAIN = "postoffice.test"
SECRET = "test-secret-with-enough-length-for-hs256"


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret=SECRET, mail_domain=DOMAIN, master_password="x")


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def stores() -> FakeStoreFactory:
    return FakeStoreFactory()


@pytest.fixture
def transport(stores, users) -> FakeTransport:
    return FakeTransport(stores, users)


@pytest.fixture
def services(settings, users, stores, transport):
    return build_services(
        settings, users=users, stores=stores, transport=transport, hasher=PasswordHasher(rounds=4)
    )


@pytest.fixture
def app(settings, services):
    app = create_app(settings, services)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register(client):
    def _register(username: str, name: str = "Test User", password: str = "password123"):
        res = client.post(
            "/api/auth/register",
            json={"name": name, "username": username, "password": password},
        )
        assert res.status_code == 201, res.get_json()
        login = client.post(
            "/api/auth/login", json={"email": f"{username}@{DOMAIN}", "password": password}
        )
        return {"Authorization": f"Bearer {login.get_json()['token']}"}

    return _register
