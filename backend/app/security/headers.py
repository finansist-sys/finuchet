"""Security headers, request size limit and safe access logging.

Two header sets: the strictest one for API/webhook responses, and a page policy for the Mini App
when the backend itself serves the static files (single-container hosting such as Railway).
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("app.access")

MAX_BODY_BYTES = 64 * 1024

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

API_HEADERS = {
    **COMMON_HEADERS,
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

PAGE_CSP = (
    "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'self' https://web.telegram.org; base-uri 'none'; form-action 'none'; object-src 'none'"
)

PAGE_HEADERS = {
    **COMMON_HEADERS,
    "Content-Security-Policy": PAGE_CSP,
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

API_PREFIXES = ("/api/", "/tg/", "/healthz")


def is_api_path(path: str) -> bool:
    return path.startswith(API_PREFIXES)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        length = request.headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
            return JSONResponse({"detail": "request too large"}, status_code=413)

        response = await call_next(request)
        path = request.url.path
        if is_api_path(path):
            headers = API_HEADERS
        else:
            headers = PAGE_HEADERS
            cache = "public, max-age=31536000, immutable" if path.startswith("/assets/") else "no-cache"
            response.headers.setdefault("Cache-Control", cache)
        for name, value in headers.items():
            response.headers.setdefault(name, value)

        # Route template ("/api/transactions/{tx_id}"), never the real path/query.
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")
        log.info(
            "%s %s %s %.0fms",
            request.method,
            template,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
