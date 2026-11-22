"""Request bodies validated with pydantic and turned into uniform 422 errors."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from flask import Request
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from postoffice_api.errors import ApiError

LOCAL_PART_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,30}[a-z0-9])?$")
ADDRESS_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,30}[a-z0-9])?@[a-z0-9.-]+\.[a-z]{2,}$")

MAX_ADDRESS_LENGTH = 254  # RFC 5321 path limit
# Local parts that belong to the system or to well-known role accounts.
RESERVED_LOCAL_PARTS = frozenset(
    {
        "abuse",
        "admin",
        "administrator",
        "api",
        "hostmaster",
        "mailer-daemon",
        "noc",
        "no-reply",
        "noreply",
        "postmaster",
        "root",
        "security",
        "support",
        "webmaster",
    }
)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_BODY_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _single_line(value: str) -> str:
    """Header-bound text (names, subjects) must not carry CR/LF or other controls."""
    if _CONTROL_RE.search(value):
        raise ValueError("must not contain line breaks or control characters")
    return value


def _clean_body(value: str) -> str:
    if _BODY_CONTROL_RE.search(value):
        raise ValueError("must not contain control characters")
    return value


SingleLine = AfterValidator(_single_line)
Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _not_reserved(value: str) -> str:
    if value in RESERVED_LOCAL_PARTS:
        raise ValueError("this address is reserved")
    return value


class RegisterRequest(_Body):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80), SingleLine
    ]
    username: Annotated[
        str,
        BeforeValidator(lambda v: v.strip().lower() if isinstance(v, str) else v),
        StringConstraints(pattern=LOCAL_PART_RE.pattern),
        AfterValidator(_not_reserved),
    ]
    password: Annotated[str, Field(min_length=8, max_length=72)]

    @model_validator(mode="after")
    def _password_fits_bcrypt(self) -> RegisterRequest:
        if len(self.password.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes")
        return self


class LoginRequest(_Body):
    email: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, to_lower=True, min_length=1, max_length=MAX_ADDRESS_LENGTH
        ),
    ]
    password: Annotated[str, Field(min_length=1, max_length=1024)]


class MessageRef(_Body):
    folder: Literal["inbox", "sent", "drafts", "archive", "trash"]
    uid: Annotated[int, Field(gt=0)]


Recipient = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, min_length=1, max_length=MAX_ADDRESS_LENGTH
    ),
]


class DraftRequest(_Body):
    to: Annotated[list[Recipient], Field(max_length=20)] = []
    cc: Annotated[list[Recipient], Field(max_length=20)] = []
    subject: Annotated[Trimmed, Field(max_length=200), SingleLine] = ""
    body: Annotated[str, Field(max_length=50_000), AfterValidator(_clean_body)] = ""
    reply_to: MessageRef | None = None
    draft_uid: Annotated[int, Field(gt=0)] | None = None


class ComposeRequest(DraftRequest):
    to: Annotated[list[Recipient], Field(min_length=1, max_length=20)]


class FlagsRequest(_Body):
    seen: bool | None = None
    flagged: bool | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> FlagsRequest:
        if self.seen is None and self.flagged is None:
            raise ValueError("provide 'seen' and/or 'flagged'")
        return self


class MoveRequest(_Body):
    target: Literal["inbox", "archive", "trash"]


def parse_body[M: BaseModel](model: type[M], request: Request) -> M:
    payload = request.get_json(silent=True)
    if payload is None:
        raise ApiError(400, "invalid_json", "Request body must be a JSON object")
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"]) or None,
                "message": err["msg"].removeprefix("Value error, "),
            }
            for err in exc.errors()
        ]
        raise ApiError(422, "validation_error", "Invalid request body", details) from None


def normalize_address(value: str, domain: str, field: str) -> str:
    """Accept ``ana`` or ``ana@<domain>``; reject anything outside the lab domain."""
    address = value if "@" in value else f"{value}@{domain}"
    if not ADDRESS_RE.match(address):
        raise ApiError(
            422, "validation_error", "Invalid address", [{"field": field, "message": value}]
        )
    if address.split("@", 1)[1] != domain:
        raise ApiError(
            422,
            "external_recipient",
            f"Only @{domain} addresses can be reached from this lab",
            [{"field": field, "message": value}],
        )
    return address
