"""In-memory test doubles for the user repository, IMAP store and SMTP transport."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from email.message import EmailMessage

from postoffice_api.errors import ApiError, not_found
from postoffice_api.mail.folders import FOLDERS
from postoffice_api.mail.mime import parse_message
from postoffice_api.mail.model import FolderStats, MessageDetail, Page
from postoffice_api.users import User


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def get(self, email: str) -> User | None:
        return self.users.get(email)

    def add(self, user: User) -> bool:
        if user.email in self.users:
            return False
        self.users[user.email] = user
        return True

    def list_all(self) -> list[User]:
        return sorted(self.users.values(), key=lambda u: u.full_name)


@dataclass
class StoredMessage:
    raw: bytes
    flags: set[str] = field(default_factory=set)


class FakeMailbox:
    """Mimics the subset of IMAP semantics the service relies on."""

    def __init__(self) -> None:
        self.folders: dict[str, dict[int, StoredMessage]] = {f: {} for f in FOLDERS}
        self.next_uid: dict[str, int] = dict.fromkeys(FOLDERS, 1)

    def deliver(self, folder: str, raw: bytes, flags: set[str] | None = None) -> int:
        uid = self.next_uid[folder]
        self.next_uid[folder] += 1
        self.folders[folder][uid] = StoredMessage(raw, set(flags or ()))
        return uid

    def _get(self, folder: str, uid: int) -> StoredMessage:
        try:
            return self.folders[folder][uid]
        except KeyError:
            raise not_found("Message not found") from None

    def _detail(self, folder: str, uid: int) -> MessageDetail:
        stored = self._get(folder, uid)
        return parse_message(uid, folder, stored.flags, stored.raw)

    # MailStore protocol
    def stats(self) -> list[FolderStats]:
        return [
            FolderStats(
                id=f,
                total=len(msgs),
                unread=sum(1 for m in msgs.values() if "\\Seen" not in m.flags),
            )
            for f, msgs in self.folders.items()
        ]

    def list_messages(self, folder: str, query: str | None, offset: int, limit: int) -> Page:
        uids = sorted(self.folders[folder], reverse=True)
        if query:
            needle = query.lower()
            uids = [
                u
                for u in uids
                if needle in self.folders[folder][u].raw.decode("utf-8", "replace").lower()
            ]
        window = uids[offset : offset + limit]
        return Page(
            items=[self._detail(folder, u).summary for u in window],
            total=len(uids),
            offset=offset,
            limit=limit,
        )

    def get_message(self, folder: str, uid: int) -> MessageDetail:
        return self._detail(folder, uid)

    def find_by_message_id(self, folder: str, message_id: str) -> int | None:
        for uid in self.folders[folder]:
            if self._detail(folder, uid).message_id == message_id:
                return uid
        return None

    def update_flags(self, folder: str, uid: int, changes: dict[str, bool]) -> None:
        stored = self._get(folder, uid)
        for flag, enabled in changes.items():
            (stored.flags.add if enabled else stored.flags.discard)(flag)

    def move(self, folder: str, uid: int, target: str) -> None:
        stored = self._get(folder, uid)
        del self.folders[folder][uid]
        self.deliver(target, stored.raw, stored.flags)

    def expunge(self, folder: str, uid: int) -> None:
        self._get(folder, uid)
        del self.folders[folder][uid]

    def append(self, folder: str, raw: bytes, flags: list[str]) -> int | None:
        return self.deliver(folder, raw, set(flags))


class FakeStoreFactory:
    def __init__(self) -> None:
        self.mailboxes: dict[str, FakeMailbox] = {}

    def mailbox(self, email: str) -> FakeMailbox:
        return self.mailboxes.setdefault(email, FakeMailbox())

    @contextmanager
    def open(self, user_email: str):
        yield self.mailbox(user_email)


class FakeTransport:
    """Delivers to the recipients' fake INBOX, refusing unknown users like Postfix."""

    def __init__(self, stores: FakeStoreFactory, users: FakeUserRepository) -> None:
        self.stores = stores
        self.users = users
        self.sent: list[tuple[str, list[str], EmailMessage]] = []

    def send(self, sender: str, recipients: list[str], message: EmailMessage) -> None:
        refused = [
            {"field": "to", "value": r, "reason": "5.1.1 User unknown"}
            for r in recipients
            if self.users.get(r) is None
        ]
        if refused:
            raise ApiError(422, "unknown_recipient", "Some recipients do not exist", refused)
        self.sent.append((sender, recipients, message))
        for rcpt in recipients:
            self.stores.mailbox(rcpt).deliver("inbox", message.as_bytes())
