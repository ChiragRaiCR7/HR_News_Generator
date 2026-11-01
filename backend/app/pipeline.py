"""Refresh run orchestration: search, deduplicate, store, analyze, record the outcome."""

import asyncio
import logging
import math

from .analysis import Analyzer, ArticleInput, BatchResult
from .db import utcnow
from .news import FetchedArticle, NewsSource, NewsSourceError
from .store import Store

log = logging.getLogger(__name__)

SEARCH_CONCURRENCY = 3


class RefreshService:
    """Starts at most one background refresh and owns its task until it finishes."""

    def __init__(
        self,
        store: Store,
        news: NewsSource | None,
        analyzer: Analyzer | None,
        batch_size: int,
        concurrency: int,
    ) -> None:
        self.store = store
        self.news = news
        self.analyzer = analyzer
        self._batch_size = batch_size
        self._concurrency = concurrency
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, keywords: list[str], max_results: int, analyze: bool) -> int:
        """Records the run (raises RunAlreadyActive if one is running) and schedules it."""
        run = await asyncio.to_thread(self.store.create_run, keywords, max_results, analyze)
        task = asyncio.create_task(
            self._execute(run.id, keywords, max_results, analyze), name=f"refresh-{run.id}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return run.id

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _execute(
        self, run_id: int, keywords: list[str], max_results: int, analyze: bool
    ) -> None:
        try:
            status = await self._refresh(run_id, keywords, max_results, analyze)
            await asyncio.to_thread(
                self.store.update_run, run_id, status=status, phase="done", finished_at=utcnow()
            )
        except asyncio.CancelledError:
            await asyncio.to_thread(
                self.store.update_run,
                run_id,
                status="failed",
                phase="done",
                finished_at=utcnow(),
                error="Cancelled: server shutting down.",
            )
            raise
        except Exception as exc:
            log.exception("refresh run %d crashed", run_id)
            await asyncio.to_thread(
                self.store.update_run,
                run_id,
                status="failed",
                phase="done",
                finished_at=utcnow(),
                error=f"Internal error: {type(exc).__name__}",
            )

    async def _refresh(
        self, run_id: int, keywords: list[str], max_results: int, analyze: bool
    ) -> str:
        warnings: list[str] = []
        fetched = await self._search_all(keywords, max_results, warnings)
        if not fetched and len(warnings) == len(keywords):
            await asyncio.to_thread(
                self.store.update_run,
                run_id,
                warnings=warnings,
                error="Every keyword search failed.",
            )
            return "failed"

        will_analyze = analyze and self.analyzer is not None
        if analyze and self.analyzer is None:
            warnings.append("GEMINI_API_KEY is not set; articles were stored without analysis.")
        ids, new = await asyncio.to_thread(
            self.store.upsert_articles, fetched, run_id, "pending" if will_analyze else "skipped"
        )
        await asyncio.to_thread(
            self.store.update_run,
            run_id,
            fetched=len(ids),
            new=new,
            warnings=warnings,
            phase="analyzing" if will_analyze else "done",
        )
        if not will_analyze:
            return "partial" if warnings else "succeeded"

        pending = await asyncio.to_thread(self.store.articles_needing_analysis, ids)
        await asyncio.to_thread(self.store.update_run, run_id, to_analyze=len(pending))
        failed = await self._analyze_all(run_id, pending)
        if failed:
            warnings.append(
                f"Analysis failed for {failed} article(s); "
                "they will be retried on the next refresh that finds them."
            )
            await asyncio.to_thread(self.store.update_run, run_id, warnings=warnings)
        return "partial" if warnings else "succeeded"

    async def _search_all(
        self, keywords: list[str], max_results: int, warnings: list[str]
    ) -> list[tuple[str, FetchedArticle]]:
        assert self.news is not None
        news = self.news
        per_keyword = math.ceil(max_results / len(keywords))
        gate = asyncio.Semaphore(SEARCH_CONCURRENCY)

        async def one(keyword: str) -> list[FetchedArticle]:
            async with gate:
                try:
                    return await news.search(keyword, per_keyword)
                except NewsSourceError as exc:
                    warnings.append(f"Search for “{keyword}” failed: {exc}")
                    return []

        results = await asyncio.gather(*(one(k) for k in keywords))
        merged: dict[str, tuple[str, FetchedArticle]] = {}
        for keyword, articles in zip(keywords, results, strict=True):
            for article in articles:
                merged.setdefault(article.url, (keyword, article))
        return list(merged.values())[:max_results]

    async def _analyze_all(self, run_id: int, pending: list[ArticleInput]) -> int:
        """Analyzes in bounded-concurrency batches, persisting each batch as it lands."""
        assert self.analyzer is not None
        analyzer = self.analyzer
        gate = asyncio.Semaphore(self._concurrency)
        batches = [
            pending[i : i + self._batch_size] for i in range(0, len(pending), self._batch_size)
        ]
        failed_total = 0

        async def one(batch: list[ArticleInput]) -> None:
            nonlocal failed_total
            async with gate:
                try:
                    result = await analyzer.analyze(batch)
                except Exception:
                    # One bad batch must not strand the rest of the run's articles in 'pending'.
                    log.exception("analysis batch crashed in run %d", run_id)
                    result = BatchResult(failures={a.id: "internal analysis error" for a in batch})
            await asyncio.to_thread(self.store.save_analyses, result.analyses, analyzer.model)
            for reason in set(result.failures.values()):
                ids = [i for i, r in result.failures.items() if r == reason]
                await asyncio.to_thread(self.store.mark_analysis, ids, "failed", reason)
            failed_total += len(result.failures)
            await asyncio.to_thread(
                self.store.add_run_progress,
                run_id,
                analyzed=len(result.analyses),
                analysis_failed=len(result.failures),
                prompt_tokens=result.prompt_tokens,
                output_tokens=result.output_tokens,
            )

        await asyncio.gather(*(one(b) for b in batches))
        return failed_total
