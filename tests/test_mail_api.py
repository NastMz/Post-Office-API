from __future__ import annotations

import pytest


@pytest.fixture
def ana(register):
    return register("ana", name="Ana Torres")


@pytest.fixture
def bruno(register):
    return register("bruno", name="Bruno Díaz")


def send(client, headers, **payload):
    payload.setdefault("subject", "Hola")
    payload.setdefault("body", "Cuerpo del mensaje")
    return client.post("/api/messages", json=payload, headers=headers)


def inbox(client, headers, **params):
    return client.get("/api/folders/inbox/messages", query_string=params, headers=headers)


def test_mail_endpoints_require_authentication(client):
    assert client.get("/api/folders").status_code == 401
    assert client.post("/api/messages", json={}).status_code == 401


def test_send_delivers_to_recipient_and_keeps_a_sent_copy(client, ana, bruno, transport):
    res = send(client, ana, to=["bruno"], subject="Laboratorio", body="Línea 1\n  Línea 2")
    assert res.status_code == 201
    assert res.get_json() == {"status": "sent", "sent_uid": 1}

    sender, recipients, message = transport.sent[0]
    assert sender == "ana@postoffice.test"
    assert recipients == ["bruno@postoffice.test"]
    assert message["From"] == "Ana Torres <ana@postoffice.test>"

    received = inbox(client, bruno).get_json()["messages"][0]
    assert received["subject"] == "Laboratorio"
    assert received["from"] == {"name": "Ana Torres", "email": "ana@postoffice.test"}
    assert received["seen"] is False

    sent = client.get("/api/folders/sent/messages", headers=ana).get_json()
    assert sent["total"] == 1 and sent["messages"][0]["seen"] is True

    body = client.get("/api/folders/inbox/messages/1", headers=bruno).get_json()["message"]
    assert body["body"] == "Línea 1\n  Línea 2"


def test_send_to_unknown_recipient_is_rejected_and_nothing_is_stored(client, ana, stores):
    res = send(client, ana, to=["ghost"])
    assert res.status_code == 422
    error = res.get_json()["error"]
    assert error["code"] == "unknown_recipient"
    assert error["details"][0]["value"] == "ghost@postoffice.test"
    assert stores.mailbox("ana@postoffice.test").folders["sent"] == {}


def test_send_rejects_external_domains_and_empty_recipients(client, ana):
    res = send(client, ana, to=["someone@example.com"])
    assert res.status_code == 422
    assert res.get_json()["error"]["code"] == "external_recipient"
    res = send(client, ana, to=[])
    assert res.status_code == 422
    assert res.get_json()["error"]["details"][0]["field"] == "to"


def test_cc_recipients_receive_a_single_copy(client, ana, bruno, register, transport):
    carla = register("carla", name="Carla")
    send(client, ana, to=["bruno", "carla"], cc=["carla"])
    assert transport.sent[0][1] == ["bruno@postoffice.test", "carla@postoffice.test"]
    assert inbox(client, carla).get_json()["total"] == 1


def test_folders_report_totals_and_unread(client, ana, bruno):
    send(client, ana, to=["bruno"])
    send(client, ana, to=["bruno"])
    folders = {f["id"]: f for f in client.get("/api/folders", headers=bruno).get_json()["folders"]}
    assert list(folders) == ["inbox", "sent", "drafts", "archive", "trash"]
    assert folders["inbox"] == {"id": "inbox", "total": 2, "unread": 2}


def test_list_is_newest_first_paginated_and_searchable(client, ana, bruno):
    for subject in ("Redes", "Protocolos", "Sockets"):
        send(client, ana, to=["bruno"], subject=subject, body=f"Tema: {subject}")
    page = inbox(client, bruno, limit=2).get_json()
    assert [m["subject"] for m in page["messages"]] == ["Sockets", "Protocolos"]
    assert page["total"] == 3
    page2 = inbox(client, bruno, limit=2, offset=2).get_json()
    assert [m["subject"] for m in page2["messages"]] == ["Redes"]
    found = inbox(client, bruno, q="protocolos").get_json()
    assert [m["subject"] for m in found["messages"]] == ["Protocolos"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 500}, {"offset": -1}, {"limit": "x"}])
def test_invalid_pagination_is_422(client, ana, params):
    res = inbox(client, ana, **params)
    assert res.status_code == 422
    assert res.get_json()["error"]["details"][0]["field"] in {"limit", "offset"}


def test_unknown_folder_and_message_are_404(client, ana):
    assert client.get("/api/folders/spam/messages", headers=ana).status_code == 404
    res = client.get("/api/folders/inbox/messages/99", headers=ana)
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"


def test_flags_can_be_set_and_cleared(client, ana, bruno):
    send(client, ana, to=["bruno"])
    url = "/api/folders/inbox/messages/1"
    res = client.patch(url, json={"seen": True, "flagged": True}, headers=bruno)
    assert res.status_code == 200
    message = res.get_json()["message"]
    assert message["seen"] is True and message["flagged"] is True
    message = client.patch(url, json={"flagged": False}, headers=bruno).get_json()["message"]
    assert message["seen"] is True and message["flagged"] is False
    assert client.patch(url, json={}, headers=bruno).status_code == 422


def test_archive_and_restore(client, ana, bruno):
    send(client, ana, to=["bruno"], subject="Guardar")
    res = client.post(
        "/api/folders/inbox/messages/1/move", json={"target": "archive"}, headers=bruno
    )
    assert res.status_code == 200
    assert inbox(client, bruno).get_json()["total"] == 0
    archived = client.get("/api/folders/archive/messages", headers=bruno).get_json()
    assert archived["messages"][0]["subject"] == "Guardar"
    uid = archived["messages"][0]["uid"]
    client.post(
        f"/api/folders/archive/messages/{uid}/move", json={"target": "inbox"}, headers=bruno
    )
    assert inbox(client, bruno).get_json()["total"] == 1


def test_invalid_moves_are_rejected(client, ana, bruno):
    send(client, ana, to=["bruno"])
    same = client.post(
        "/api/folders/inbox/messages/1/move", json={"target": "inbox"}, headers=bruno
    )
    assert same.status_code == 422
    sent_to_inbox = client.post(
        "/api/folders/sent/messages/1/move", json={"target": "inbox"}, headers=ana
    )
    assert sent_to_inbox.get_json()["error"]["code"] == "invalid_move"
    bad_target = client.post(
        "/api/folders/inbox/messages/1/move", json={"target": "sent"}, headers=bruno
    )
    assert bad_target.status_code == 422


def test_delete_moves_to_trash_then_deletes_permanently(client, ana, bruno, stores):
    send(client, ana, to=["bruno"])
    res = client.delete("/api/folders/inbox/messages/1", headers=bruno)
    assert res.get_json() == {"status": "trashed"}
    trash = client.get("/api/folders/trash/messages", headers=bruno).get_json()
    assert trash["total"] == 1
    uid = trash["messages"][0]["uid"]
    res = client.delete(f"/api/folders/trash/messages/{uid}", headers=bruno)
    assert res.get_json() == {"status": "deleted"}
    mailbox = stores.mailbox("bruno@postoffice.test")
    assert all(not messages for messages in mailbox.folders.values())


def test_reply_threads_headers_and_marks_original_answered(client, ana, bruno, transport):
    send(client, ana, to=["bruno"], subject="Pregunta")
    original = client.get("/api/folders/inbox/messages/1", headers=bruno).get_json()["message"]
    res = send(
        client,
        bruno,
        to=["ana"],
        subject="Re: Pregunta",
        body="Respuesta",
        reply_to={"folder": "inbox", "uid": 1},
    )
    assert res.status_code == 201
    reply = transport.sent[-1][2]
    assert reply["In-Reply-To"] == original["message_id"]
    assert original["message_id"] in reply["References"]
    flagged = client.get("/api/folders/inbox/messages/1", headers=bruno).get_json()["message"]
    assert flagged["answered"] is True


def test_drafts_are_saved_replaced_and_removed_when_sent(client, ana, bruno):
    res = client.post("/api/drafts", json={"subject": "Borrador", "body": "v1"}, headers=ana)
    assert res.status_code == 201
    first = res.get_json()["draft_uid"]
    res = client.post(
        "/api/drafts",
        json={"to": ["bruno"], "subject": "Borrador", "body": "v2", "draft_uid": first},
        headers=ana,
    )
    second = res.get_json()["draft_uid"]
    drafts = client.get("/api/folders/drafts/messages", headers=ana).get_json()
    assert [m["uid"] for m in drafts["messages"]] == [second]
    assert drafts["messages"][0]["draft"] is True

    send(client, ana, to=["bruno"], subject="Borrador", body="v2", draft_uid=second)
    assert client.get("/api/folders/drafts/messages", headers=ana).get_json()["total"] == 0
    assert inbox(client, bruno).get_json()["messages"][0]["preview"] == "v2"


def test_sending_a_reply_draft_keeps_the_thread(client, ana, bruno, transport):
    send(client, ana, to=["bruno"], subject="Hilo")
    client.post(
        "/api/drafts",
        json={"to": ["ana"], "subject": "Re: Hilo", "reply_to": {"folder": "inbox", "uid": 1}},
        headers=bruno,
    )
    send(client, bruno, to=["ana"], subject="Re: Hilo", body="Listo", draft_uid=1)
    assert transport.sent[-1][2]["In-Reply-To"] is not None
    original = client.get("/api/folders/inbox/messages/1", headers=bruno).get_json()["message"]
    assert original["answered"] is True


def test_directory_lists_other_users(client, ana, bruno):
    users = client.get("/api/users", headers=ana).get_json()["users"]
    assert users == [{"email": "bruno@postoffice.test", "name": "Bruno Díaz"}]
