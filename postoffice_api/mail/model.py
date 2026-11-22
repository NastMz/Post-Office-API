"""Value objects shared by the protocol adapters, the service and the routes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Address:
    name: str
    email: str


@dataclass(frozen=True)
class MessageSummary:
    uid: int
    folder: str
    subject: str
    sender: Address | None
    to: list[Address]
    cc: list[Address]
    date: str | None
    preview: str
    seen: bool
    flagged: bool
    answered: bool
    draft: bool

    def to_dict(self) -> dict:
        data = asdict(self)
        data["from"] = data.pop("sender")
        return data


@dataclass(frozen=True)
class MessageDetail:
    summary: MessageSummary
    body: str
    message_id: str | None
    references: list[str] = field(default_factory=list)
    in_reply_to: str | None = None

    def to_dict(self) -> dict:
        data = self.summary.to_dict()
        data.update(
            body=self.body,
            message_id=self.message_id,
            in_reply_to=self.in_reply_to,
            references=self.references,
        )
        return data


@dataclass(frozen=True)
class FolderStats:
    id: str
    total: int
    unread: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Page:
    items: list[MessageSummary]
    total: int
    offset: int
    limit: int

    def to_dict(self) -> dict:
        return {
            "messages": [m.to_dict() for m in self.items],
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
        }
