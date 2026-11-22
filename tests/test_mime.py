from __future__ import annotations

from email.message import EmailMessage

from postoffice_api.mail.mime import build_message, make_preview, parse_message, reply_subject
from postoffice_api.mail.model import Address

ANA = Address("Ana Torres", "ana@postoffice.test")
BRUNO = Address("Bruno Díaz", "bruno@postoffice.test")


def test_build_and_parse_round_trip_keeps_utf8_and_whitespace():
    msg = build_message(
        sender=ANA,
        to=[BRUNO],
        cc=[],
        subject="Revisión de «IMAP»",
        body="Hola\n\n    código indentado\nÚltima línea",
        domain="postoffice.test",
    )
    detail = parse_message(7, "inbox", {"\\Seen", "\\Flagged"}, msg.as_bytes())
    s = detail.summary
    assert s.uid == 7 and s.folder == "inbox"
    assert s.subject == "Revisión de «IMAP»"
    assert s.sender == ANA
    assert s.to == [BRUNO]
    assert s.seen and s.flagged and not s.answered and not s.draft
    assert detail.body == "Hola\n\n    código indentado\nÚltima línea"
    assert detail.message_id.endswith("@postoffice.test>")
    assert s.date is not None


def test_reply_headers_build_a_reference_chain():
    msg = build_message(
        sender=ANA,
        to=[BRUNO],
        cc=[BRUNO],
        subject="Re: x",
        body="ok",
        domain="postoffice.test",
        in_reply_to="<b@x>",
        references=["<a@x>", "<b@x>"],
    )
    assert msg["In-Reply-To"] == "<b@x>"
    assert msg["References"] == "<a@x> <b@x>"
    assert "bruno@postoffice.test" in msg["Cc"]


def test_html_only_messages_are_flattened_to_text():
    msg = EmailMessage()
    msg["From"] = "x@postoffice.test"
    msg["Subject"] = "html"
    msg.set_content("<p>Hola &amp; <b>adiós</b></p>", subtype="html")
    detail = parse_message(1, "inbox", set(), msg.as_bytes())
    assert detail.body == "Hola & adiós"


def test_missing_headers_and_bad_dates_are_tolerated():
    raw = b"Subject: solo asunto\r\nDate: not a date\r\n\r\ncuerpo\r\n"
    detail = parse_message(1, "drafts", set(), raw)
    assert detail.summary.sender is None
    assert detail.summary.date is None
    assert detail.summary.draft is True  # everything in Drafts is a draft


def test_preview_collapses_whitespace_and_truncates():
    assert make_preview("a\n\n  b\tc") == "a b c"
    long = make_preview("palabra " * 50)
    assert len(long) == 140 and long.endswith("…")


def test_reply_subject_is_not_duplicated():
    assert reply_subject("Hola") == "Re: Hola"
    assert reply_subject("RE: Hola") == "RE: Hola"
