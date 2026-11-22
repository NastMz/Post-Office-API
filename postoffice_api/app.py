"""Flask application factory and dependency wiring."""

from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, jsonify
from flask_cors import CORS

from postoffice_api.config import Settings
from postoffice_api.errors import register_error_handlers
from postoffice_api.mail.imap_store import ImapStoreFactory
from postoffice_api.mail.smtp_transport import SmtpTransport
from postoffice_api.ratelimit import TrustedProxies, limiter
from postoffice_api.routes import auth, mail
from postoffice_api.security import PasswordHasher, TokenService
from postoffice_api.services import AuthService, MailService, MailStoreFactory, Transport
from postoffice_api.users import MariaDbUserRepository, UserRepository


@dataclass
class Services:
    users: UserRepository
    auth: AuthService
    mail: MailService


def build_services(
    settings: Settings,
    *,
    users: UserRepository | None = None,
    stores: MailStoreFactory | None = None,
    transport: Transport | None = None,
    hasher: PasswordHasher | None = None,
) -> Services:
    users = users or MariaDbUserRepository(
        settings.db_host, settings.db_port, settings.db_user, settings.db_password, settings.db_name
    )
    stores = stores or ImapStoreFactory(
        settings.mail_host, settings.imap_port, settings.master_user, settings.master_password
    )
    transport = transport or SmtpTransport(
        settings.mail_host, settings.smtp_port, settings.master_user, settings.master_password
    )
    tokens = TokenService(settings.jwt_secret, settings.token_ttl_minutes)
    return Services(
        users=users,
        auth=AuthService(users, hasher or PasswordHasher(), tokens, settings.mail_domain),
        mail=MailService(stores, transport, users, settings.mail_domain),
    )


def create_app(settings: Settings | None = None, services: Services | None = None) -> Flask:
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.extensions["postoffice"] = services or build_services(settings)
    app.config["MAIL_DOMAIN"] = settings.mail_domain
    app.config["MAX_CONTENT_LENGTH"] = settings.max_body_bytes
    app.config["AUTH_RATE_LIMIT"] = settings.auth_rate_limit
    app.extensions["postoffice_proxies"] = TrustedProxies(settings.trusted_proxies)
    limiter.init_app(app)
    if settings.cors_origins:
        CORS(app, resources={r"/api/*": {"origins": list(settings.cors_origins)}})

    register_error_handlers(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(mail.bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "domain": settings.mail_domain})

    return app
