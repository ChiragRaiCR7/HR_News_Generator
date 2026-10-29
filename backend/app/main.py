"""Application factory: wires settings, SQLite, providers, routes, and the built SPA."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .analysis import Analyzer, GeminiAnalyzer
from .api import router
from .config import Settings, get_settings
from .db import init_db, make_engine
from .news import NewsSource, SerpApiNews
from .pipeline import RefreshService
from .store import Store

log = logging.getLogger("app")

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    # Outbound article links must not leak which dashboard the reader came from.
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
Providers = tuple[NewsSource | None, Analyzer | None]


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx logs full request URLs at INFO, and SerpAPI URLs carry the API key.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None, providers: Providers | None = None) -> FastAPI:
    """Builds the app; `providers` overrides the SerpAPI/Gemini clients (used by tests)."""
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_path)
        store = Store(init_db(engine))
        if interrupted := store.fail_interrupted_runs():
            log.warning("marked %d interrupted refresh run(s) as failed", interrupted)
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
            if providers is not None:
                news, analyzer = providers
            else:
                news = (
                    SerpApiNews(settings.serpapi_key.get_secret_value(), http)
                    if settings.serpapi_key
                    else None
                )
                analyzer = (
                    GeminiAnalyzer(
                        settings.gemini_api_key.get_secret_value(), settings.gemini_model
                    )
                    if settings.gemini_api_key
                    else None
                )
            app.state.settings = settings
            app.state.refresh = RefreshService(
                store, news, analyzer, settings.analysis_batch_size, settings.analysis_concurrency
            )
            log.info(
                "ready: db=%s serpapi=%s gemini=%s model=%s",
                settings.database_path,
                news is not None,
                analyzer is not None,
                settings.gemini_model,
            )
            try:
                yield
            finally:
                await app.state.refresh.shutdown()
        engine.dispose()

    app = FastAPI(title="HR News Intelligence", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.include_router(router)
    mount_spa(app, settings.frontend_dist)
    return app


def mount_spa(app: FastAPI, dist: Path) -> None:
    """Serves the built frontend, falling back to index.html for client-side routes."""
    index = dist / "index.html"
    if not index.is_file():
        log.info("no built frontend at %s; serving the API only", dist)
        return
    root = dist.resolve()
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
