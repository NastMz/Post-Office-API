"""End-to-end test against the running docker compose stack.

    docker compose up -d --build
    pytest -m integration

Talks to the real API (8151), which talks SMTP/IMAP to Postfix/Dovecot.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid

import pytest

pytestmark = pytest.mark.integration

BASE = os.environ.get("POSTOFFICE_API_URL", "http://localhost:8151/api")


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=30) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def test_register_send_and_receive_through_smtp_and_imap():
    user = f"it{uuid.uuid4().hex[:8]}"
    status, _ = call(
        "POST", "/auth/register", {"name": "Prueba", "username": user, "password": "integration1"}
    )
    assert status == 201
    _, login = call("POST", "/auth/login", {"email": user, "password": "integration1"})
    token = login["token"]

    status, _ = call("POST", "/messages", {"to": [user], "subject": "Eco", "body": "ping"}, token)
    assert status == 201
    for _ in range(20):
        _, page = call("GET", "/folders/inbox/messages", token=token)
        if page["total"]:
            break
        time.sleep(0.5)
    assert page["messages"][0]["subject"] == "Eco"

    status, err = call("POST", "/messages", {"to": ["nobody-here"], "subject": "x"}, token)
    assert status == 422 and err["error"]["code"] == "unknown_recipient"
