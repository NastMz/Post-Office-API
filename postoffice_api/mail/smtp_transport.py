"""SMTP submission (RFC 6409) with SASL AUTH PLAIN against Postfix on port 587.

The SMTP dialogue is driven step by step (EHLO, AUTH, MAIL FROM, RCPT TO,
DATA) so that recipients refused by the server are reported precisely and
nothing is delivered when any recipient is rejected.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from postoffice_api.errors import ApiError
from postoffice_api.mail.imap_store import MailServerUnavailable


class SmtpTransport:
    def __init__(self, host: str, port: int, master_user: str, master_password: str) -> None:
        self._host = host
        self._port = port
        self._master_user = master_user
        self._master_password = master_password

    def send(self, sender: str, recipients: list[str], message: EmailMessage) -> None:
        try:
            server = smtplib.SMTP(self._host, self._port, timeout=15)
        except OSError as exc:
            raise MailServerUnavailable(str(exc)) from exc
        try:
            server.ehlo("api.postoffice")
            server.login(f"{sender}*{self._master_user}", self._master_password)
            code, reply = server.mail(sender)
            if code != 250:
                raise ApiError(502, "smtp_error", f"MAIL FROM refused: {reply.decode()}")
            refused = []
            for rcpt in recipients:
                code, reply = server.rcpt(rcpt)
                if code not in (250, 251):
                    refused.append({"field": "to", "value": rcpt, "reason": reply.decode()})
            if refused:
                server.rset()
                raise ApiError(422, "unknown_recipient", "Some recipients do not exist", refused)
            code, reply = server.data(message.as_bytes())
            if code != 250:
                raise ApiError(502, "smtp_error", f"DATA refused: {reply.decode()}")
        except smtplib.SMTPAuthenticationError as exc:
            raise ApiError(502, "smtp_auth_failed", "Mail server rejected the session") from exc
        except smtplib.SMTPException as exc:
            raise ApiError(502, "smtp_error", str(exc)) from exc
        finally:
            try:
                server.quit()
            except (smtplib.SMTPException, OSError):
                server.close()
