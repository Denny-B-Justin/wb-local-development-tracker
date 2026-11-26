"""Input standardization, HTTP hardening and rate limiting."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import threading
import time
from collections import defaultdict, deque
from urllib.parse import parse_qsl, urlparse

from flask import Flask, Response, request

import constants

from .text import clean

log = logging.getLogger(__name__)

ALLOWED_PARAMS = {
    "page", "lang", "country", "year", "compare", "unit", "tab", "trend", "pillar", "indicator", "selected",
    "x", "y", "size", "base", "view", "q", "sort", "dir", "scope", "score",
}
_PARAM_VALUE = re.compile(r"^[\w\-., ':/()&+%À-ɏḀ-ỿ]*$", re.UNICODE)


def parse_query(search: str | None, level_keys: tuple[str, ...] = ()) -> dict[str, str]:
    """Validated, first-wins query params. Unknown keys and odd values are dropped."""
    text = (search or "").lstrip("?")[: constants.MAX_QUERY_STRING_LENGTH]
    allowed = ALLOWED_PARAMS | set(level_keys)
    out: dict[str, str] = {}
    for key, value in parse_qsl(text, keep_blank_values=False):
        if key not in allowed or key in out:
            continue
        value = clean(value, constants.MAX_SEARCH_LENGTH if key == "q" else 120)
        if key != "q" and not _PARAM_VALUE.fullmatch(value):
            continue
        if value:
            out[key] = value
    return out


def slug(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value if constants.SLUG_PATTERN.fullmatch(value) else None


def unit_id(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value if constants.UNIT_ID_PATTERN.fullmatch(value) else None


def compare_ids(value: str | None) -> list[str]:
    ids: list[str] = []
    for part in (value or "").split(","):
        uid = unit_id(part)
        if uid and uid not in ids:
            ids.append(uid)
    return ids[: constants.COMPARE_MAX]


def choice(value: str | None, options, default):
    return value if value in options else default


def safe_external_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value.strip()


def constant_time_equals(expected: str, provided: str | None) -> bool:
    return bool(expected) and provided is not None and hmac.compare_digest(expected.encode(), provided.encode())


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            if len(self._hits) > 50_000:
                for stale in [k for k, v in self._hits.items() if not v][:10_000]:
                    self._hits.pop(stale, None)
            return True

    def used(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            return sum(1 for t in self._hits.get(key, ()) if now - t <= self.window)


api_limiter = RateLimiter(constants.API_RATE_LIMIT_PER_MINUTE, 60)


def client_key() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    address = forwarded.split(",")[0].strip() or request.remote_addr or "unknown"
    return hashlib.sha256(address.encode()).hexdigest()[:24]


def same_origin() -> bool:
    """The browser's Origin (or Referer) names this site. Behind a proxy (Posit Connect) the request's
    Host can be the internal address, so the host the proxy forwarded (X-Forwarded-Host) also counts."""
    origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
    hosts = {request.host, *(h.strip() for h in request.headers.get("X-Forwarded-Host", "").split(",") if h.strip())}
    host = urlparse(origin).netloc if origin else ""
    if host and (host in hosts or origin.rstrip("/") in constants.ALLOWED_ORIGINS):
        return True
    log.warning("Rejected %s %s: origin %r does not match host %s (set LDT_ALLOWED_ORIGINS to allow it)", request.method, request.path,
                urlparse(origin)._replace(path="", query="", fragment="").geturl() if origin else None, sorted(hosts))
    return False


def content_security_policy(script_hashes: list[str]) -> str:
    scripts = " ".join(h if h.startswith("'") else f"'{h}'" for h in script_hashes)
    return "; ".join([
        "default-src 'self'",
        f"script-src 'self' {scripts}",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "child-src 'self' blob:",
        "frame-ancestors 'self'",
        "form-action 'self'",
        "base-uri 'self'",
        "object-src 'none'",
    ])


def harden(server: Flask, script_hashes: list[str]) -> None:
    """Security headers, CORS lockdown and exposed-file protection for every response."""
    csp = content_security_policy(script_hashes)
    blocked = re.compile(r"(^|/)(\.env|\.git|\.ldt_cache|data_snapshot|services|locales|scripts|countries|manifest\.json|requirements\.txt)(/|$)|\.(py|pyc|gz|map)$")

    @server.before_request
    def _guard():
        path = request.path
        if blocked.search(path.lstrip("/")) and not path.startswith(("/assets/", "/_dash", "/api/")):
            return Response("Not found", status=404)
        if len(request.query_string) > constants.MAX_QUERY_STRING_LENGTH:
            return Response("Request too long", status=414)
        if path.startswith("/api/") and not api_limiter.hit(client_key()):
            return Response("Too many requests", status=429, headers={"Retry-After": "60"})
        return None

    @server.after_request
    def _headers(response: Response) -> Response:
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
            response.headers["Strict-Transport-Security"] = f"max-age={constants.HSTS_SECONDS}; includeSubDomains"
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") in constants.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        else:
            response.headers.pop("Access-Control-Allow-Origin", None)
        response.headers.pop("Server", None)
        if request.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response
