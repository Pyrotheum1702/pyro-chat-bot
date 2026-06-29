"""Security helpers: filename sanitization, security headers, and rate limiting.

Proportionate hardening for a local/self-hosted app — not a substitute for a
reverse proxy + TLS + auth in a real deployment (see SECURITY.md).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

logger = logging.getLogger("ragchat")

# ---------------------------------------------------------------------------
# Filename safety (defends against path traversal on upload)
# ---------------------------------------------------------------------------
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def safe_filename(name: str) -> str:
    """Reduce an uploaded filename to a safe basename.

    Strips any directory components ("../", absolute paths) and unusual
    characters so a malicious filename can't escape the upload directory.
    """
    base = Path(name or "").name           # drop directory parts
    base = _UNSAFE_CHARS.sub("_", base)    # neutralize odd characters
    base = base.lstrip(".")                # no leading dots / hidden files
    if not base or base in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    return base[:200]


def ensure_within(directory: Path, candidate: Path) -> Path:
    """Belt-and-suspenders: confirm `candidate` resolves inside `directory`."""
    d = directory.resolve()
    c = candidate.resolve()
    if c != d and d not in c.parents:
        raise HTTPException(status_code=400, detail="Invalid file path.")
    return c


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # The SPA is served same-origin; styles are injected inline by the bundler.
        h.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        return response


# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per client IP, fixed window)
# ---------------------------------------------------------------------------
class _RateLimiter:
    def __init__(self, limit: int, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._hits: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= now - self.window:
                dq.popleft()
            if len(dq) >= self.limit:
                raise HTTPException(
                    status_code=429, detail="Rate limit exceeded — slow down."
                )
            dq.append(now)


_limiter: "_RateLimiter | None" = None


def _get_limiter() -> _RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = _RateLimiter(get_settings().rate_limit_per_minute)
    return _limiter


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def rate_limit(request: Request) -> None:
    """FastAPI dependency: throttle expensive endpoints per client IP."""
    if not get_settings().rate_limit_enabled:
        return
    _get_limiter().check(_client_ip(request))
