"""HTTP routes under /api."""

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from . import __version__
from .pipeline import RefreshService
from .schemas import (
    ArticleOut,
    ArticlePage,
    Health,
    Insights,
    NameCount,
    RefreshRequest,
    RunOut,
    Sentiment,
)
from .store import ArticleFilters, RunAlreadyActive

router = APIRouter(prefix="/api")


def service(request: Request) -> RefreshService:
    svc: RefreshService = request.app.state.refresh
    return svc


@router.get("/health")
def health(request: Request) -> Health:
    svc = service(request)
    return Health(
        status="ok",
        version=__version__,
        serpapi_configured=svc.news is not None,
        gemini_configured=svc.analyzer is not None,
        model=request.app.state.settings.gemini_model,
    )


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(body: RefreshRequest, request: Request) -> RunOut:
    svc = service(request)
    if svc.news is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "News search is not configured. Set SERPAPI_KEY in backend/.env "
            "and restart the server.",
        )
    try:
        run_id = await svc.start(body.keywords, body.max_results, body.analyze)
    except RunAlreadyActive:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A refresh is already running. Wait for it to finish."
        ) from None
    run = await asyncio.to_thread(svc.store.get_run, run_id)
    return RunOut.model_validate(run)


@router.get("/runs")
def list_runs(request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> list[RunOut]:
    return [RunOut.model_validate(r) for r in service(request).store.list_runs(limit)]


@router.get("/runs/{run_id}")
def get_run(run_id: int, request: Request) -> RunOut:
    run = service(request).store.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found.")
    return RunOut.model_validate(run)


@router.get("/articles")
def list_articles(
    request: Request,
    sentiment: Annotated[list[Sentiment], Query()] = [],  # noqa: B006 - FastAPI copies defaults
    source: Annotated[list[str], Query(max_length=200)] = [],  # noqa: B006
    min_relevance: Annotated[int | None, Query(ge=1, le=10)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    analyzed_only: bool = False,
    sort: Literal["newest", "relevance"] = "newest",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ArticlePage:
    filters = ArticleFilters(
        sentiments=sentiment,
        sources=source,
        min_relevance=min_relevance,
        query=(q or "").strip() or None,
        analyzed_only=analyzed_only,
    )
    items, total = service(request).store.list_articles(filters, sort, limit, offset)
    return ArticlePage(
        items=[ArticleOut.model_validate(a) for a in items], total=total, limit=limit, offset=offset
    )


@router.get("/sources")
def list_sources(request: Request) -> list[NameCount]:
    return [NameCount(name=n, count=c) for n, c in service(request).store.list_sources()]


@router.get("/insights")
def insights(request: Request, days: Annotated[int, Query(ge=1, le=365)] = 30) -> Insights:
    return Insights.model_validate(service(request).store.insights(days))
