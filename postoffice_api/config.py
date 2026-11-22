"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    mail_domain: str = "postoffice.test"
    mail_host: str = "localhost"
    imap_port: int = 143
    smtp_port: int = 587
    master_user: str = "api"
    master_password: str = ""
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "postoffice"
    db_user: str = "postoffice"
    db_password: str = ""
    token_ttl_minutes: int = 480
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    seed_demo_data: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get
        origins = tuple(o.strip() for o in env("CORS_ORIGINS", "").split(",") if o.strip())
        return cls(
            jwt_secret=_require("JWT_SECRET"),
            mail_domain=env("MAIL_DOMAIN", "postoffice.test"),
            mail_host=env("MAIL_HOST", "localhost"),
            imap_port=int(env("IMAP_PORT", "143")),
            smtp_port=int(env("SMTP_PORT", "587")),
            master_user=env("MAIL_MASTER_USER", "api"),
            master_password=_require("MAIL_MASTER_PASSWORD"),
            db_host=env("DB_HOST", "localhost"),
            db_port=int(env("DB_PORT", "3306")),
            db_name=env("DB_NAME", "postoffice"),
            db_user=env("DB_USER", "postoffice"),
            db_password=env("DB_PASSWORD", ""),
            token_ttl_minutes=int(env("TOKEN_TTL_MINUTES", "480")),
            cors_origins=origins,
            seed_demo_data=env("SEED_DEMO_DATA", "false").lower() in {"1", "true", "yes"},
        )
