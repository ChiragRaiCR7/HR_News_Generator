import asyncio
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analysis import ArticleAnalysis, ArticleInput, BatchResult
from app.config import Settings
from app.main import create_app
from app.news import FetchedArticle, NewsSourceError

NOW = datetime.now(UTC)


def article(n: int, *, source: str = "HR Dive", hours_ago: int = 1) -> FetchedArticle:
    return FetchedArticle(
        url=f"https://news.example/{n}",
        title=f"Story {n}",
        source=source,
        snippet=f"Snippet about pay transparency {n}",
        published_at=NOW - timedelta(hours=hours_ago),
    )


class FakeNews:
    def __init__(self, results: dict[str, list[FetchedArticle] | Exception]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    async def search(self, keyword: str, limit: int) -> list[FetchedArticle]:
        self.calls.append((keyword, limit))
        result = self.results.get(keyword, [])
        if isinstance(result, Exception):
            raise result
        return result[:limit]


class FakeAnalyzer:
    model = "fake-model"

    def __init__(self, drop_ids: set[int] | None = None, gate: "Gate | None" = None) -> None:
        self.drop_ids = drop_ids or set()
        self.analyzed: list[int] = []
        self.gate = gate

    async def analyze(self, batch: list[ArticleInput]) -> BatchResult:
        if self.gate:
            await self.gate.wait()
        result = BatchResult(prompt_tokens=10 * len(batch), output_tokens=5 * len(batch))
        for a in batch:
            self.analyzed.append(a.id)
            if a.id in self.drop_ids:
                result.failures[a.id] = "missing from model output"
            else:
                result.analyses[a.id] = ArticleAnalysis(
                    id=a.id,
                    summary=f"Summary of {a.title}",
                    themes=["Pay Transparency", "Law"],
                    sentiment=("positive", "neutral", "negative")[a.id % 3],
                    relevance=min(10, a.id + 4),
                )
        return result


class Gate:
    """Lets a test hold an analysis batch open until it releases it."""

    def __init__(self) -> None:
        self.open = False

    async def wait(self) -> None:
        # Polling, not asyncio.Event: the test thread flips the flag outside the event loop.
        while not self.open:  # noqa: ASYNC110
            await asyncio.sleep(0.01)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "test.db",
        frontend_dist=tmp_path / "no-dist",
        serpapi_key=None,
        gemini_api_key=None,
        analysis_batch_size=2,
    )


def make_client(
    settings: Settings, news: FakeNews | None, analyzer: FakeAnalyzer | None
) -> TestClient:
    return TestClient(create_app(settings, providers=(news, analyzer)))


@pytest.fixture
def news() -> FakeNews:
    return FakeNews(
        {
            "HR trends": [article(1), article(2, source="SHRM"), article(3)],
            "talent acquisition": [article(3), article(4, source="SHRM", hours_ago=30)],
        }
    )


@pytest.fixture
def analyzer() -> FakeAnalyzer:
    return FakeAnalyzer()


@pytest.fixture
def client(settings: Settings, news: FakeNews, analyzer: FakeAnalyzer) -> Iterator[TestClient]:
    with make_client(settings, news, analyzer) as c:
        yield c


def wait_for_run(client: TestClient, run_id: int, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} still running after {timeout}s")


__all__ = ["FakeNews", "Gate", "NewsSourceError", "article", "make_client", "wait_for_run"]
