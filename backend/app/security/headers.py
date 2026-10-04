"""Security headers, request size limit and safe access logging for the API."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("app.access")

MAX_BODY_BYTES = 64 * 1024

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        length = request.headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
            return JSONResponse({"detail": "request too large"}, status_code=413)

        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)

        # Route template ("/api/transactions/{tx_id}"), never the real path/query.
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        log.info(
            "%s %s %s %.0fms",
            request.method,
            path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response
