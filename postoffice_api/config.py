"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Values shipped in docker-compose.yml for local development. They are public,
# so the API refuses them unless APP_ENV=development is set explicitly.
DEV_DEFAULT_SECRETS = frozenset(
    {
        "dev-only-secret-change-me-in-production",
        "master-dev",
        "change-me",
        "change-me-to-a-long-random-string",
    }
)


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
    app_env: str = "production"
    max_body_bytes: int = 256 * 1024
    auth_rate_limit: str = "10 per minute"
    trusted_proxies: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    def check_secrets(self) -> None:
        """Refuse the well-known development secrets outside development."""
        if self.is_development:
            return
        weak = [
            name
            for name, value in (
                ("JWT_SECRET", self.jwt_secret),
                ("MAIL_MASTER_PASSWORD", self.master_password),
            )
            if value in DEV_DEFAULT_SECRETS
        ]
        if weak:
            raise RuntimeError(
                f"{', '.join(weak)} still use the public development defaults; "
                "set real secrets (see .env.example) or APP_ENV=development"
            )

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get

        def _list(name: str) -> tuple[str, ...]:
            return tuple(v.strip() for v in env(name, "").split(",") if v.strip())

        settings = cls(
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
            cors_origins=_list("CORS_ORIGINS"),
            seed_demo_data=env("SEED_DEMO_DATA", "false").lower() in {"1", "true", "yes"},
            app_env=env("APP_ENV", "production").lower(),
            auth_rate_limit=env("AUTH_RATE_LIMIT", "10 per minute"),
            trusted_proxies=_list("TRUSTED_PROXIES"),
        )
        settings.check_secrets()
        return settings
