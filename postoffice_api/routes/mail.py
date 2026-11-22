"""Mailbox endpoints: folders, messages, flags, moves, sending and drafts."""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from postoffice_api.errors import ApiError
from postoffice_api.mail.folders import mailbox_for
from postoffice_api.routes.auth import login_required
from postoffice_api.schemas import (
    ComposeRequest,
    DraftRequest,
    FlagsRequest,
    MoveRequest,
    parse_body,
)
from postoffice_api.services import MailService

bp = Blueprint("mail", __name__, url_prefix="/api")

MAX_PAGE = 100


def mail_service() -> MailService:
    return current_app.extensions["postoffice"].mail


def _int_arg(name: str, default: int, low: int, high: int) -> int:
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = low - 1
    if not low <= value <= high:
        raise ApiError(
            422,
            "validation_error",
            "Invalid query parameter",
            [{"field": name, "message": f"must be an integer between {low} and {high}"}],
        )
    return value


@bp.get("/users")
@login_required
def directory():
    users = current_app.extensions["postoffice"].users.list_all()
    return jsonify({"users": [u.public() for u in users if u.email != g.user.email]})


@bp.get("/folders")
@login_required
def folders():
    return jsonify({"folders": [f.to_dict() for f in mail_service().folders(g.user)]})


@bp.get("/folders/<folder>/messages")
@login_required
def list_messages(folder: str):
    mailbox_for(folder)
    query = request.args.get("q", "").strip()[:200]
    offset = _int_arg("offset", 0, 0, 1_000_000)
    limit = _int_arg("limit", 50, 1, MAX_PAGE)
    page = mail_service().list(g.user, folder, query, offset, limit)
    return jsonify(page.to_dict())


@bp.get("/folders/<folder>/messages/<int:uid>")
@login_required
def read_message(folder: str, uid: int):
    mailbox_for(folder)
    return jsonify({"message": mail_service().read(g.user, folder, uid).to_dict()})


@bp.patch("/folders/<folder>/messages/<int:uid>")
@login_required
def update_flags(folder: str, uid: int):
    mailbox_for(folder)
    body = parse_body(FlagsRequest, request)
    summary = mail_service().set_flags(g.user, folder, uid, body.seen, body.flagged)
    return jsonify({"message": summary.to_dict()})


@bp.post("/folders/<folder>/messages/<int:uid>/move")
@login_required
def move_message(folder: str, uid: int):
    mailbox_for(folder)
    body = parse_body(MoveRequest, request)
    mail_service().move(g.user, folder, uid, body.target)
    return jsonify({"status": "moved", "target": body.target})


@bp.delete("/folders/<folder>/messages/<int:uid>")
@login_required
def delete_message(folder: str, uid: int):
    mailbox_for(folder)
    outcome = mail_service().delete(g.user, folder, uid)
    return jsonify({"status": outcome})


@bp.post("/messages")
@login_required
def send_message():
    body = parse_body(ComposeRequest, request)
    uid = mail_service().send(g.user, body)
    return jsonify({"status": "sent", "sent_uid": uid}), 201


@bp.post("/drafts")
@login_required
def save_draft():
    body = parse_body(DraftRequest, request)
    uid = mail_service().save_draft(g.user, body)
    return jsonify({"status": "saved", "draft_uid": uid}), 201
