"""Authentication endpoints and the ``login_required`` decorator."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request

from postoffice_api.errors import unauthorized
from postoffice_api.ratelimit import limiter
from postoffice_api.schemas import LoginRequest, RegisterRequest, parse_body
from postoffice_api.services import AuthService

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def auth_service() -> AuthService:
    return current_app.extensions["postoffice"].auth


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise unauthorized()
        g.user = auth_service().authenticate(token.strip())
        return view(*args, **kwargs)

    return wrapper


def _auth_limit() -> str:
    return current_app.config["AUTH_RATE_LIMIT"]


@bp.post("/register")
@limiter.limit(_auth_limit)
def register():
    body = parse_body(RegisterRequest, request)
    user = auth_service().register(body.name, body.username, body.password)
    return jsonify({"user": user.public()}), 201


@bp.post("/login")
@limiter.limit(_auth_limit)
def login():
    body = parse_body(LoginRequest, request)
    token, user = auth_service().login(body.email, body.password)
    return jsonify({"token": token, "user": user.public()})


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.user.public()})
