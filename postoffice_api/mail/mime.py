"""RFC 5322 / MIME composition and parsing (no network access here)."""

from __future__ import annotations

import html
import re
from email import message_from_bytes, policy
from email.headerregistry import Address as HeaderAddress
from email.message import EmailMessage
from email.utils import format_datetime, getaddresses, localtime, make_msgid, parsedate_to_datetime

from postoffice_api.mail.model import Address, MessageDetail, MessageSummary

PREVIEW_LENGTH = 140
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def format_address(address: Address) -> str:
    local, _, domain = address.email.partition("@")
    return str(HeaderAddress(display_name=address.name, username=local, domain=domain))


def build_message(
    *,
    sender: Address,
    to: list[Address],
    cc: list[Address],
    subject: str,
    body: str,
    domain: str,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> EmailMessage:
    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = format_address(sender)
    msg["To"] = ", ".join(format_address(a) for a in to)
    if cc:
        msg["Cc"] = ", ".join(format_address(a) for a in cc)
    msg["Subject"] = subject
    msg["Date"] = format_datetime(localtime())
    msg["Message-ID"] = make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        chain = [r for r in (references or []) if r != in_reply_to]
        msg["References"] = " ".join([*chain, in_reply_to])
    msg["User-Agent"] = "Post Office/1.0"
    msg.set_content(body)
    return msg


def reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _addresses(values: list[str]) -> list[Address]:
    return [
        Address(name=name, email=email.lower()) for name, email in getaddresses(values) if email
    ]


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return None


def extract_text(msg) -> str:
    """Return the best plain-text representation of a parsed message."""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_subtype() == "html":
        content = html.unescape(_TAG_RE.sub("", content))
    return content.replace("\r\n", "\n").rstrip()


def make_preview(text: str) -> str:
    flat = _SPACE_RE.sub(" ", text).strip()
    return flat if len(flat) <= PREVIEW_LENGTH else flat[: PREVIEW_LENGTH - 1].rstrip() + "…"


def parse_message(uid: int, folder: str, flags: set[str], raw: bytes) -> MessageDetail:
    msg = message_from_bytes(raw, policy=policy.default)
    senders = _addresses(msg.get_all("From", []))
    body = extract_text(msg)
    summary = MessageSummary(
        uid=uid,
        folder=folder,
        subject=str(msg.get("Subject", "")).strip(),
        sender=senders[0] if senders else None,
        to=_addresses(msg.get_all("To", [])),
        cc=_addresses(msg.get_all("Cc", [])),
        date=_iso_date(msg.get("Date")),
        preview=make_preview(body),
        seen="\\Seen" in flags,
        flagged="\\Flagged" in flags,
        answered="\\Answered" in flags,
        draft="\\Draft" in flags or folder == "drafts",
    )
    references = str(msg.get("References", "")).split()
    message_id = msg.get("Message-ID")
    in_reply_to = msg.get("In-Reply-To")
    return MessageDetail(
        summary=summary,
        body=body,
        message_id=str(message_id).strip() if message_id else None,
        references=references,
        in_reply_to=str(in_reply_to).strip() if in_reply_to else None,
    )
