"""Password hashing (bcrypt, Dovecot-compatible) and JWT session tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from postoffice_api.errors import unauthorized

# Dovecot reads the same column, so the hash carries its scheme prefix.
SCHEME_PREFIX = "{BLF-CRYPT}"


class PasswordHasher:
    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash(self, password: str) -> str:
        digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(self._rounds))
        return SCHEME_PREFIX + digest.decode("ascii")

    def verify(self, password: str, stored: str) -> bool:
        if not stored.startswith(SCHEME_PREFIX):
            return False
        digest = stored[len(SCHEME_PREFIX) :].encode("ascii")
        try:
            return bcrypt.checkpw(password.encode("utf-8"), digest)
        except ValueError:
            return False


class TokenService:
    """Issues short-lived HS256 tokens that identify a user (never a password)."""

    algorithm = "HS256"

    def __init__(self, secret: str, ttl_minutes: int) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 characters long")
        self._secret = secret
        self._ttl = timedelta(minutes=ttl_minutes)

    def issue(self, email: str, now: datetime | None = None) -> str:
        issued = now or datetime.now(UTC)
        claims = {"sub": email, "iat": issued, "exp": issued + self._ttl}
        return jwt.encode(claims, self._secret, algorithm=self.algorithm)

    def verify(self, token: str) -> str:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self.algorithm],
                options={"require": ["sub", "exp", "iat"]},
            )
        except jwt.ExpiredSignatureError:
            raise unauthorized("Session expired") from None
        except jwt.InvalidTokenError:
            raise unauthorized("Invalid session token") from None
        return str(claims["sub"])
