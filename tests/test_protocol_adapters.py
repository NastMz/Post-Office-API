"""Unit tests for the IMAP and SMTP adapters using scripted protocol doubles."""

from __future__ import annotations

import smtplib

import pytest

from postoffice_api.errors import ApiError
from postoffice_api.mail import smtp_transport
from postoffice_api.mail.imap_store import ImapStore, parse_fetch
from postoffice_api.mail.mime import build_message
from postoffice_api.mail.model import Address

RAW = build_message(
    sender=Address("Ana", "ana@postoffice.test"),
    to=[Address("Bruno", "bruno@postoffice.test")],
    cc=[],
    subject="Asunto",
    body="Hola",
    domain="postoffice.test",
).as_bytes()


def test_parse_fetch_handles_flags_before_and_after_the_literal():
    data = [
        (b"1 (UID 4 FLAGS (\\Seen \\Flagged) BODY[] {10}", RAW),
        b")",
        (b"2 (UID 9 BODY[] {10}", RAW),
        b" FLAGS (\\Answered))",
    ]
    parsed = parse_fetch(data)
    assert [(uid, flags) for uid, flags, _ in parsed] == [
        (4, {"\\Seen", "\\Flagged"}),
        (9, {"\\Answered"}),
    ]
    assert parsed[0][2] == RAW


class ScriptedImap:
    """Records commands and replies like imaplib.IMAP4 would."""

    def __init__(self, uids=(1, 2, 3)) -> None:
        self.calls: list[tuple] = []
        self.literal = None
        self.uids = list(uids)

    def select(self, mailbox):
        self.calls.append(("SELECT", mailbox))
        return "OK", [b"3"]

    def status(self, mailbox, items):
        return "OK", [f'"{mailbox}" (MESSAGES 5 UNSEEN 2)'.encode()]

    def uid(self, command, *args):
        self.calls.append((command, *args, self.literal))
        literal, self.literal = self.literal, None
        if command == "SEARCH":
            return "OK", [" ".join(map(str, self.uids)).encode()]
        if command == "FETCH":
            requested = [int(u) for u in args[0].split(",")]
            data = []
            for u in requested:
                if u in self.uids:
                    data += [(f"{u} (UID {u} FLAGS () BODY[] {{1}}".encode(), RAW), b")"]
            return "OK", data or [None]
        if command == "MOVE" and literal is None:
            return "OK", [b"[COPYUID 1 1 1] Moved"]
        return "OK", [b"done"]

    def append(self, mailbox, flags, date, raw):
        self.calls.append(("APPEND", mailbox, flags))
        return "OK", [b"[APPENDUID 1700000000 42] Append completed."]

    def logout(self):
        self.calls.append(("LOGOUT",))


def test_list_selects_folder_searches_and_pages_newest_first():
    conn = ScriptedImap(uids=(1, 2, 3))
    page = ImapStore(conn).list_messages("sent", None, offset=0, limit=2)
    assert conn.calls[0] == ("SELECT", "Sent")
    assert [m.uid for m in page.items] == [3, 2]
    assert page.total == 3
    fetch = next(c for c in conn.calls if c[0] == "FETCH")
    assert fetch[1] == "3,2"


def test_search_sends_the_term_as_a_utf8_literal():
    conn = ScriptedImap()
    ImapStore(conn).list_messages("inbox", 'redes ñ "x"', 0, 10)
    search = next(c for c in conn.calls if c[0] == "SEARCH")
    assert search == ("SEARCH", "CHARSET", "UTF-8", "TEXT", 'redes ñ "x"'.encode())


def test_status_append_and_expunge_commands():
    conn = ScriptedImap()
    store = ImapStore(conn)
    stats = {s.id: s for s in store.stats()}
    assert stats["trash"].total == 5 and stats["trash"].unread == 2
    assert store.append("drafts", RAW, ["\\Draft", "\\Seen"]) == 42
    assert ("APPEND", "Drafts", "(\\Draft \\Seen)") in conn.calls
    store.expunge("trash", 2)
    commands = [c[:4] for c in conn.calls if c[0] in {"STORE", "EXPUNGE"}]
    assert commands == [("STORE", "2", "+FLAGS.SILENT", "(\\Deleted)"), ("EXPUNGE", "2", None)]


def test_missing_uid_is_404_and_server_errors_are_502():
    store = ImapStore(ScriptedImap(uids=(1,)))
    with pytest.raises(ApiError) as missing:
        store.move("inbox", 99, "trash")
    assert missing.value.status == 404

    class Failing(ScriptedImap):
        def select(self, mailbox):
            return "NO", [b"Mailbox does not exist"]

    with pytest.raises(ApiError) as failed:
        ImapStore(Failing()).get_message("inbox", 1)
    assert failed.value.status == 502
    assert "Mailbox does not exist" in failed.value.message


class ScriptedSmtp:
    instances: list[ScriptedSmtp] = []
    refuse: set[str] = set()

    def __init__(self, host, port, timeout):
        self.dialog: list[tuple] = []
        ScriptedSmtp.instances.append(self)

    def ehlo(self, name):
        self.dialog.append(("EHLO", name))

    def login(self, user, password):
        self.dialog.append(("AUTH", user))

    def mail(self, sender):
        self.dialog.append(("MAIL", sender))
        return 250, b"2.1.0 Ok"

    def rcpt(self, rcpt):
        self.dialog.append(("RCPT", rcpt))
        if rcpt in self.refuse:
            return 550, b"5.1.1 User unknown in virtual mailbox table"
        return 250, b"2.1.5 Ok"

    def rset(self):
        self.dialog.append(("RSET",))

    def data(self, raw):
        self.dialog.append(("DATA",))
        return 250, b"2.0.0 Ok: queued"

    def quit(self):
        self.dialog.append(("QUIT",))


@pytest.fixture
def smtp(monkeypatch):
    ScriptedSmtp.instances.clear()
    ScriptedSmtp.refuse = set()
    monkeypatch.setattr(smtp_transport.smtplib, "SMTP", ScriptedSmtp)
    return smtp_transport.SmtpTransport("mail", 587, "api", "secret")


def test_smtp_dialog_authenticates_as_master_for_the_sender(smtp):
    from email import message_from_bytes, policy

    message = message_from_bytes(RAW, policy=policy.default)
    smtp.send("ana@postoffice.test", ["bruno@postoffice.test"], message)
    assert ScriptedSmtp.instances[0].dialog == [
        ("EHLO", "api.postoffice"),
        ("AUTH", "ana@postoffice.test*api"),
        ("MAIL", "ana@postoffice.test"),
        ("RCPT", "bruno@postoffice.test"),
        ("DATA",),
        ("QUIT",),
    ]


def test_smtp_refused_recipient_aborts_before_data(smtp):
    from email import message_from_bytes, policy

    ScriptedSmtp.refuse = {"ghost@postoffice.test"}
    message = message_from_bytes(RAW, policy=policy.default)
    with pytest.raises(ApiError) as err:
        smtp.send(
            "ana@postoffice.test", ["bruno@postoffice.test", "ghost@postoffice.test"], message
        )
    assert err.value.status == 422
    assert err.value.details[0]["value"] == "ghost@postoffice.test"
    dialog = ScriptedSmtp.instances[0].dialog
    assert ("RSET",) in dialog and ("DATA",) not in dialog


def test_smtp_unreachable_server_is_503(monkeypatch):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(smtp_transport.smtplib, "SMTP", refuse)
    with pytest.raises(ApiError) as err:
        smtp_transport.SmtpTransport("mail", 587, "api", "x").send("a", ["b"], None)
    assert err.value.status == 503


def test_smtp_auth_failure_is_502(monkeypatch, smtp):
    def bad_login(self, user, password):
        raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed")

    monkeypatch.setattr(ScriptedSmtp, "login", bad_login)
    with pytest.raises(ApiError) as err:
        smtp.send("ana@postoffice.test", ["bruno@postoffice.test"], None)
    assert err.value.code == "smtp_auth_failed"
