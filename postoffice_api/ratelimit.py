"""Per-client rate limiting for the authentication endpoints.

The client is identified by its socket address. ``X-Forwarded-For`` is only
honoured when the request comes from a configured trusted proxy (the nginx
container of the web client); anyone talking to the API port directly cannot
spoof their address with that header.
"""

from __future__ import annotations

import socket
import time

from flask import current_app, request
from flask_limiter import Limiter


class TrustedProxies:
    """Resolves proxy host names (e.g. ``web``) to IPs, refreshing on a miss."""

    def __init__(self, hosts: tuple[str, ...], refresh_seconds: float = 30.0) -> None:
        self._hosts = hosts
        self._refresh = refresh_seconds
        self._ips: set[str] = set()
        self._resolved_at = float("-inf")

    def _resolve(self) -> None:
        ips: set[str] = set()
        for host in self._hosts:
            try:
                ips.update(socket.gethostbyname_ex(host)[2])
            except OSError:
                continue
        self._ips = ips
        self._resolved_at = time.monotonic()

    def contains(self, address: str | None) -> bool:
        if not self._hosts or not address:
            return False
        if address in self._ips:
            return True
        if time.monotonic() - self._resolved_at > self._refresh:
            self._resolve()
        return address in self._ips


def client_ip() -> str:
    remote = request.remote_addr or "unknown"
    proxies: TrustedProxies = current_app.extensions["postoffice_proxies"]
    if proxies.contains(remote):
        forwarded = request.headers.get("X-Forwarded-For", "")
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]  # the address nginx itself appended
    return remote


limiter = Limiter(key_func=client_ip, storage_uri="memory://", headers_enabled=True)
