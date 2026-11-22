"""Uniform error type and JSON error envelope.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": [...]}}
"""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


def not_found(message: str = "Resource not found") -> ApiError:
    return ApiError(404, "not_found", message)


def unauthorized(message: str = "Authentication required") -> ApiError:
    return ApiError(401, "unauthorized", message)


def _payload(code: str, message: str, details: list[dict[str, Any]] | None = None):
    return {"error": {"code": code, "message": message, "details": details or []}}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return jsonify(_payload(err.code, err.message, err.details)), err.status

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        code = (err.name or "error").lower().replace(" ", "_")
        return jsonify(_payload(code, err.description or err.name)), err.code

    @app.errorhandler(Exception)
    def _unexpected(err: Exception):
        app.logger.exception("Unhandled error", exc_info=err)
        return jsonify(_payload("internal_error", "Unexpected server error")), 500
