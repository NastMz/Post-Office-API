"""Use cases: account management and mailbox operations.

The services only talk to abstractions (a user repository, a mailbox store
factory and an SMTP transport) so they can be tested without a mail server.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from email.message import EmailMessage
from typing import Protocol

from postoffice_api.errors import ApiError
from postoffice_api.mail.mime import build_message
from postoffice_api.mail.model import Address, FolderStats, MessageDetail, Page
from postoffice_api.schemas import ComposeRequest, DraftRequest, normalize_address
from postoffice_api.security import PasswordHasher, TokenService
from postoffice_api.users import User, UserRepository

FLAG_NAMES = {"seen": "\\Seen", "flagged": "\\Flagged"}


class MailStore(Protocol):
    def stats(self) -> list[FolderStats]: ...
    def list_messages(self, folder: str, query: str | None, offset: int, limit: int) -> Page: ...
    def get_message(self, folder: str, uid: int) -> MessageDetail: ...
    def find_by_message_id(self, folder: str, message_id: str) -> int | None: ...
    def update_flags(self, folder: str, uid: int, changes: dict[str, bool]) -> None: ...
    def move(self, folder: str, uid: int, target: str) -> None: ...
    def expunge(self, folder: str, uid: int) -> None: ...
    def append(self, folder: str, raw: bytes, flags: list[str]) -> int | None: ...


class MailStoreFactory(Protocol):
    def open(self, user_email: str) -> AbstractContextManager[MailStore]: ...


class Transport(Protocol):
    def send(self, sender: str, recipients: list[str], message: EmailMessage) -> None: ...


class AuthService:
    def __init__(
        self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService, domain: str
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._domain = domain

    def register(self, name: str, username: str, password: str) -> User:
        user = User(
            email=f"{username}@{self._domain}",
            full_name=name,
            password_hash=self._hasher.hash(password),
        )
        if not self._users.add(user):
            raise ApiError(
                409,
                "email_taken",
                "That address is already registered",
                [{"field": "username", "message": user.email}],
            )
        return user

    def login(self, email: str, password: str) -> tuple[str, User]:
        address = email if "@" in email else f"{email}@{self._domain}"
        user = self._users.get(address)
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise ApiError(401, "invalid_credentials", "Wrong address or password")
        return self._tokens.issue(user.email), user

    def authenticate(self, token: str) -> User:
        email = self._tokens.verify(token)
        user = self._users.get(email)
        if user is None:
            raise ApiError(401, "unauthorized", "Account no longer exists")
        return user


class MailService:
    def __init__(
        self,
        stores: MailStoreFactory,
        transport: Transport,
        users: UserRepository,
        domain: str,
    ) -> None:
        self._stores = stores
        self._transport = transport
        self._users = users
        self._domain = domain

    # -- reading -----------------------------------------------------------
    def folders(self, user: User) -> list[FolderStats]:
        with self._stores.open(user.email) as store:
            return store.stats()

    def list(self, user: User, folder: str, query: str | None, offset: int, limit: int) -> Page:
        with self._stores.open(user.email) as store:
            return store.list_messages(folder, query or None, offset, limit)

    def read(self, user: User, folder: str, uid: int) -> MessageDetail:
        with self._stores.open(user.email) as store:
            return store.get_message(folder, uid)

    # -- organising --------------------------------------------------------
    def set_flags(self, user: User, folder: str, uid: int, seen: bool | None, flagged: bool | None):
        changes = {
            FLAG_NAMES[name]: value
            for name, value in (("seen", seen), ("flagged", flagged))
            if value is not None
        }
        with self._stores.open(user.email) as store:
            store.update_flags(folder, uid, changes)
            return store.get_message(folder, uid).summary

    def move(self, user: User, folder: str, uid: int, target: str) -> None:
        if folder == target:
            raise ApiError(422, "same_folder", "The message is already in that folder")
        if folder in {"sent", "drafts"} and target == "inbox":
            raise ApiError(422, "invalid_move", "Sent mail and drafts cannot go to the inbox")
        with self._stores.open(user.email) as store:
            store.move(folder, uid, target)

    def delete(self, user: User, folder: str, uid: int) -> str:
        """Trash/drafts delete permanently; any other folder moves to the trash."""
        with self._stores.open(user.email) as store:
            if folder in {"trash", "drafts"}:
                store.expunge(folder, uid)
                return "deleted"
            store.move(folder, uid, "trash")
            return "trashed"

    # -- writing -----------------------------------------------------------
    def _addresses(self, values: list[str], field: str) -> list[Address]:
        result: list[Address] = []
        for index, value in enumerate(values):
            email = normalize_address(value, self._domain, f"{field}.{index}")
            known = self._users.get(email)
            result.append(Address(name=known.full_name if known else "", email=email))
        return result

    def _compose(
        self, user: User, request: DraftRequest, store: MailStore
    ) -> tuple[EmailMessage, list[str]]:
        to = self._addresses(request.to, "to")
        cc = self._addresses(request.cc, "cc")
        in_reply_to, references = None, []
        if request.reply_to:
            original = store.get_message(request.reply_to.folder, request.reply_to.uid)
            in_reply_to, references = original.message_id, original.references
        elif request.draft_uid:
            draft = store.get_message("drafts", request.draft_uid)
            in_reply_to, references = draft.in_reply_to, draft.references
        message = build_message(
            sender=Address(name=user.full_name, email=user.email),
            to=to,
            cc=cc,
            subject=request.subject,
            body=request.body,
            domain=self._domain,
            in_reply_to=in_reply_to,
            references=references,
        )
        recipients = list(dict.fromkeys(a.email for a in [*to, *cc]))
        return message, recipients

    def send(self, user: User, request: ComposeRequest) -> int | None:
        with self._stores.open(user.email) as store:
            message, recipients = self._compose(user, request, store)
            self._transport.send(user.email, recipients, message)
            sent_uid = store.append("sent", message.as_bytes(), ["\\Seen"])
            self._mark_answered(store, request, message)
            if request.draft_uid:
                self._discard_draft(store, request.draft_uid)
            return sent_uid

    def save_draft(self, user: User, request: DraftRequest) -> int | None:
        with self._stores.open(user.email) as store:
            message, _ = self._compose(user, request, store)
            uid = store.append("drafts", message.as_bytes(), ["\\Draft", "\\Seen"])
            if request.draft_uid:
                self._discard_draft(store, request.draft_uid)
            return uid

    @staticmethod
    def _mark_answered(store: MailStore, request: ComposeRequest, message: EmailMessage) -> None:
        """Set \\Answered on the original message, as IMAP clients do."""
        if request.reply_to:
            store.update_flags(request.reply_to.folder, request.reply_to.uid, {"\\Answered": True})
            return
        original_id = message.get("In-Reply-To")
        if not original_id:
            return
        for folder in ("inbox", "archive"):
            uid = store.find_by_message_id(folder, str(original_id))
            if uid:
                store.update_flags(folder, uid, {"\\Answered": True})
                return

    @staticmethod
    def _discard_draft(store: MailStore, uid: int) -> None:
        try:
            store.expunge("drafts", uid)
        except ApiError as err:
            if err.status != 404:
                raise
