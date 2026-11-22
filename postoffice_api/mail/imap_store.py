"""IMAP4rev1 mailbox access (RFC 3501) with the UIDPLUS and MOVE extensions.

The API never stores user passwords: it opens each user's mailbox through a
Dovecot *master user* login (``<user>*<master>``), which the mail server only
accepts from holders of the master secret.
"""

from __future__ import annotations

import imaplib
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from postoffice_api.errors import ApiError, not_found
from postoffice_api.mail.folders import FOLDERS, mailbox_for
from postoffice_api.mail.mime import parse_message
from postoffice_api.mail.model import FolderStats, MessageDetail, Page

_UID_RE = re.compile(rb"UID (\d+)")
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)")
_STATUS_RE = re.compile(rb"MESSAGES (\d+).*?UNSEEN (\d+)")
_APPENDUID_RE = re.compile(rb"APPENDUID \d+ (\d+)")


class MailServerUnavailable(ApiError):
    def __init__(self, detail: str) -> None:
        super().__init__(503, "mail_server_unavailable", f"Mail server unavailable: {detail}")


def parse_fetch(data: list) -> list[tuple[int, set[str], bytes]]:
    """Turn an imaplib ``UID FETCH (UID FLAGS BODY.PEEK[])`` response into tuples."""
    pending: list[list[bytes]] = []
    for item in data:
        if isinstance(item, tuple):
            pending.append([item[0], item[1]])
        elif isinstance(item, bytes) and pending:
            pending[-1][0] += item  # trailing " FLAGS (...))" after the literal
    results: list[tuple[int, set[str], bytes]] = []
    for header, raw in pending:
        uid_match = _UID_RE.search(header)
        if not uid_match:
            continue
        flags_match = _FLAGS_RE.search(header)
        flags = set(flags_match.group(1).decode().split()) if flags_match else set()
        results.append((int(uid_match.group(1)), flags, raw))
    return results


class ImapStore:
    """One authenticated IMAP session for one user."""

    def __init__(self, conn: imaplib.IMAP4) -> None:
        self._conn = conn
        self._selected: str | None = None

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _check(typ: str, data: list, action: str) -> list:
        if typ != "OK":
            detail = data[0].decode(errors="replace") if data and data[0] else typ
            raise ApiError(502, "imap_error", f"IMAP {action} failed: {detail}")
        return data

    def _select(self, folder: str) -> None:
        mailbox = mailbox_for(folder)
        if self._selected != mailbox:
            self._check(*self._conn.select(mailbox), "SELECT")
            self._selected = mailbox

    def _search(self, query: str | None) -> list[int]:
        if query:
            # Send the term as a literal so quotes and UTF-8 survive intact.
            self._conn.literal = query.encode("utf-8")
            typ, data = self._conn.uid("SEARCH", "CHARSET", "UTF-8", "TEXT")
        else:
            typ, data = self._conn.uid("SEARCH", None, "ALL")
        data = self._check(typ, data, "SEARCH")
        return [int(n) for n in (data[0] or b"").split()]

    def _fetch(self, folder: str, uids: list[int]) -> list[MessageDetail]:
        if not uids:
            return []
        uid_set = ",".join(str(u) for u in uids)
        typ, data = self._conn.uid("FETCH", uid_set, "(UID FLAGS BODY.PEEK[])")
        return [
            parse_message(uid, folder, flags, raw)
            for uid, flags, raw in parse_fetch(self._check(typ, data, "FETCH"))
        ]

    # -- queries -----------------------------------------------------------
    def stats(self) -> list[FolderStats]:
        result = []
        for folder, mailbox in FOLDERS.items():
            typ, data = self._conn.status(mailbox, "(MESSAGES UNSEEN)")
            match = _STATUS_RE.search(self._check(typ, data, "STATUS")[0])
            total, unread = (int(match.group(1)), int(match.group(2))) if match else (0, 0)
            result.append(FolderStats(id=folder, total=total, unread=unread))
        return result

    def list_messages(self, folder: str, query: str | None, offset: int, limit: int) -> Page:
        self._select(folder)
        uids = sorted(self._search(query), reverse=True)
        window = uids[offset : offset + limit]
        messages = {m.summary.uid: m.summary for m in self._fetch(folder, window)}
        items = [messages[u] for u in window if u in messages]
        return Page(items=items, total=len(uids), offset=offset, limit=limit)

    def get_message(self, folder: str, uid: int) -> MessageDetail:
        self._select(folder)
        found = self._fetch(folder, [uid])
        if not found:
            raise not_found("Message not found")
        return found[0]

    def find_by_message_id(self, folder: str, message_id: str) -> int | None:
        self._select(folder)
        self._conn.literal = message_id.encode("utf-8")
        typ, data = self._conn.uid("SEARCH", "HEADER", "Message-ID")
        uids = (self._check(typ, data, "SEARCH")[0] or b"").split()
        return int(uids[-1]) if uids else None

    # -- commands ----------------------------------------------------------
    def update_flags(self, folder: str, uid: int, changes: dict[str, bool]) -> None:
        self.get_message(folder, uid)  # 404 when the UID does not exist
        for flag, enabled in changes.items():
            op = "+FLAGS.SILENT" if enabled else "-FLAGS.SILENT"
            self._check(*self._conn.uid("STORE", str(uid), op, f"({flag})"), "STORE")

    def move(self, folder: str, uid: int, target: str) -> None:
        self.get_message(folder, uid)
        self._check(*self._conn.uid("MOVE", str(uid), mailbox_for(target)), "MOVE")

    def expunge(self, folder: str, uid: int) -> None:
        self.get_message(folder, uid)
        self._check(*self._conn.uid("STORE", str(uid), "+FLAGS.SILENT", "(\\Deleted)"), "STORE")
        self._check(*self._conn.uid("EXPUNGE", str(uid)), "UID EXPUNGE")

    def append(self, folder: str, raw: bytes, flags: list[str]) -> int | None:
        typ, data = self._conn.append(
            mailbox_for(folder),
            f"({' '.join(flags)})",
            imaplib.Time2Internaldate(time.time()),
            raw,
        )
        match = _APPENDUID_RE.search(self._check(typ, data, "APPEND")[0] or b"")
        return int(match.group(1)) if match else None

    def close(self) -> None:
        with suppress(imaplib.IMAP4.error, OSError):
            self._conn.logout()


class ImapStoreFactory:
    """Opens :class:`ImapStore` sessions on behalf of a user."""

    def __init__(self, host: str, port: int, master_user: str, master_password: str) -> None:
        self._host = host
        self._port = port
        self._master_user = master_user
        self._master_password = master_password

    @contextmanager
    def open(self, user_email: str) -> Iterator[ImapStore]:
        try:
            conn = imaplib.IMAP4(self._host, self._port, timeout=15)
        except OSError as exc:
            raise MailServerUnavailable(str(exc)) from exc
        try:
            conn.login(f"{user_email}*{self._master_user}", self._master_password)
        except imaplib.IMAP4.error as exc:
            conn.shutdown()
            raise ApiError(502, "imap_auth_failed", "Mail server rejected the session") from exc
        store = ImapStore(conn)
        try:
            yield store
        finally:
            store.close()
