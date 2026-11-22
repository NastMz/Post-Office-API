"""User directory persisted in MariaDB (shared with Postfix and Dovecot)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

import pymysql
from pymysql.cursors import DictCursor

from postoffice_api.errors import ApiError


@dataclass(frozen=True)
class User:
    email: str
    full_name: str
    password_hash: str

    def public(self) -> dict:
        return {"email": self.email, "name": self.full_name}


class UserRepository(Protocol):
    def get(self, email: str) -> User | None: ...

    def add(self, user: User) -> bool:
        """Insert the user; return False when the address is already taken."""
        ...

    def list_all(self) -> list[User]: ...


class MariaDbUserRepository:
    def __init__(self, host: str, port: int, user: str, password: str, database: str) -> None:
        self._params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "connect_timeout": 10,
        }

    @contextmanager
    def _cursor(self) -> Iterator[pymysql.cursors.Cursor]:
        try:
            conn = pymysql.connect(**self._params)
        except pymysql.MySQLError as exc:
            raise ApiError(503, "database_unavailable", "User database unavailable") from exc
        try:
            with conn.cursor() as cursor:
                yield cursor
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _to_user(row: dict) -> User:
        return User(email=row["email"], full_name=row["full_name"], password_hash=row["password"])

    def get(self, email: str) -> User | None:
        with self._cursor() as cur:
            cur.execute("SELECT email, full_name, password FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
        return self._to_user(row) if row else None

    def add(self, user: User) -> bool:
        try:
            with self._cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, full_name, password) VALUES (%s, %s, %s)",
                    (user.email, user.full_name, user.password_hash),
                )
        except pymysql.IntegrityError:
            return False
        return True

    def list_all(self) -> list[User]:
        with self._cursor() as cur:
            cur.execute("SELECT email, full_name, password FROM users ORDER BY full_name")
            return [self._to_user(row) for row in cur.fetchall()]
