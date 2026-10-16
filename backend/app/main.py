"""FastAPI application: Mini App API (+ Telegram webhook, wired in app.bot)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import accounts, me, stats, transactions
from app.config import Settings, get_settings
from app.log_setup import setup_logging
from app.security.headers import SecurityMiddleware, is_api_path
from app.security.ratelimit import RateLimiter
from app.services.errors import DomainError

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Serverless platforms may skip lifespan entirely; everything here is optional:
        # the DB engine and the bot dispatcher are created lazily on first use.
        from app.bot.setup import start_bot, stop_bot

        await start_bot(app)
        try:
            yield
        finally:
            await stop_bot(app)
            engine = getattr(app.state, "engine", None)
            if engine is not None:
                await engine.dispose()

    app = FastAPI(
        title="Finuchet API",
        lifespan=lifespan,
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else "/openapi.json",
    )
    app.state.settings = settings
    app.state.api_limiter = RateLimiter(limit=120, window_seconds=60)
    app.add_middleware(SecurityMiddleware)

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": exc.code}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo submitted values back (they may contain personal notes).
        fields = sorted({".".join(str(p) for p in e.get("loc", ())[1:]) for e in exc.errors()})
        return JSONResponse({"detail": "invalid_request", "fields": fields[:10]}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            {"detail": exc.detail if isinstance(exc.detail, str) else "error"}, status_code=exc.status_code
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error: %s", type(exc).__name__)
        return JSONResponse({"detail": "internal_error"}, status_code=500)

    for router in (me.router, accounts.router, transactions.router, stats.router):
        app.include_router(router)

    from app.bot.setup import webhook_router

    app.include_router(webhook_router)

    @app.get("/healthz", include_in_schema=False)
    @app.get("/api/healthz", include_in_schema=False)
    async def healthz() -> dict:
        # Serverless: first call after a deploy migrates the DB and points Telegram at this URL.
        from app.bot.setup import ensure_bot_setup
        from app.db.session import app_sessionmaker

        await app_sessionmaker(app)
        configured = await ensure_bot_setup(app)
        return {"ok": True, "telegram_configured_now": configured}

    if settings.static_dir and Path(settings.static_dir).is_dir():
        mount_mini_app(app, Path(settings.static_dir))

    return app


def mount_mini_app(app: FastAPI, root: Path) -> None:
    """Serve the built Mini App (single-page app) from `root`, after all API routes."""
    root = root.resolve()
    index = root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def mini_app(full_path: str) -> FileResponse | JSONResponse:
        if is_api_path("/" + full_path):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (root / full_path).resolve()
        # Only files inside the build directory; anything else falls back to the SPA entry page.
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
