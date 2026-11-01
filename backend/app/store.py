"""SQLite reads and writes. Every function opens and closes its own short session."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import ColumnElement, case, func, or_, select, true, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .analysis import ArticleAnalysis, ArticleInput
from .db import Article, Run, utcnow
from .news import FetchedArticle

PUBLISHED = func.coalesce(Article.published_at, Article.first_seen_at)
LIKE_ESCAPE = "\\"


class RunAlreadyActive(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ArticleFilters:
    sentiments: Sequence[str] = ()
    sources: Sequence[str] = ()
    min_relevance: int | None = None
    query: str | None = None
    analyzed_only: bool = False


class Store:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    # ---- runs -------------------------------------------------------------

    def create_run(self, keywords: list[str], max_results: int, analyze: bool) -> Run:
        with self._sessions.begin() as s:
            run = Run(keywords=keywords, max_results=max_results, analyze=analyze, warnings=[])
            s.add(run)
            try:
                s.flush()
            except IntegrityError:
                raise RunAlreadyActive from None
            return run

    def update_run(self, run_id: int, **values: object) -> None:
        with self._sessions.begin() as s:
            s.execute(update(Run).where(Run.id == run_id).values(**values))

    def add_run_progress(self, run_id: int, **increments: int) -> None:
        with self._sessions.begin() as s:
            s.execute(
                update(Run)
                .where(Run.id == run_id)
                .values({getattr(Run, k): getattr(Run, k) + v for k, v in increments.items()})
            )

    def get_run(self, run_id: int) -> Run | None:
        with self._sessions() as s:
            return s.get(Run, run_id)

    def list_runs(self, limit: int) -> list[Run]:
        with self._sessions() as s:
            return list(s.scalars(select(Run).order_by(Run.id.desc()).limit(limit)))

    def fail_interrupted_runs(self) -> int:
        """Marks runs orphaned by a crash or restart so a new refresh can start."""
        with self._sessions.begin() as s:
            result = s.execute(
                update(Run)
                .where(Run.status == "running")
                .values(
                    status="failed",
                    phase="done",
                    finished_at=utcnow(),
                    error="Interrupted: the server stopped before this refresh finished.",
                )
            )
            return result.rowcount  # type: ignore[attr-defined, no-any-return]

    # ---- articles: writes -------------------------------------------------

    def upsert_articles(
        self, items: list[tuple[str, FetchedArticle]], run_id: int, analysis_status: str
    ) -> tuple[list[int], int]:
        """Inserts unseen URLs, refreshes last_seen_at on known ones; returns (ids, new_count)."""
        if not items:
            return [], 0
        now = utcnow()
        with self._sessions.begin() as s:
            ids: list[int] = []
            new = 0
            for keyword, a in items:
                stmt = insert(Article).values(
                    url=a.url,
                    title=a.title,
                    source=a.source,
                    snippet=a.snippet,
                    keyword=keyword,
                    published_at=a.published_at,
                    first_seen_at=now,
                    last_seen_at=now,
                    first_run_id=run_id,
                    analysis_status=analysis_status,
                    themes=[],
                )
                upsert = stmt.on_conflict_do_update(
                    index_elements=[Article.url], set_={"last_seen_at": now}
                ).returning(Article.id, Article.first_run_id)
                article_id, first_run_id = s.execute(upsert).one()
                ids.append(article_id)
                new += first_run_id == run_id
            return ids, new

    def articles_needing_analysis(self, ids: list[int]) -> list[ArticleInput]:
        with self._sessions() as s:
            rows = s.execute(
                select(Article.id, Article.title, Article.source, Article.snippet)
                .where(Article.id.in_(ids), Article.analysis_status != "done")
                .order_by(Article.id)
            )
            return [ArticleInput(*row) for row in rows]

    def save_analyses(self, analyses: dict[int, ArticleAnalysis], model: str) -> None:
        now = utcnow()
        with self._sessions.begin() as s:
            for article_id, a in analyses.items():
                s.execute(
                    update(Article)
                    .where(Article.id == article_id)
                    .values(
                        analysis_status="done",
                        summary=a.summary,
                        themes=a.themes,
                        sentiment=a.sentiment,
                        relevance=a.relevance,
                        analysis_error=None,
                        analyzed_at=now,
                        model=model,
                    )
                )

    def mark_analysis(self, ids: list[int], status: str, error: str | None = None) -> None:
        if not ids:
            return
        with self._sessions.begin() as s:
            s.execute(
                update(Article)
                .where(Article.id.in_(ids), Article.analysis_status != "done")
                .values(analysis_status=status, analysis_error=error)
            )

    # ---- articles: reads --------------------------------------------------

    @staticmethod
    def _conditions(f: ArticleFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if f.sentiments:
            conditions.append(Article.sentiment.in_(f.sentiments))
        if f.sources:
            conditions.append(Article.source.in_(f.sources))
        if f.min_relevance is not None:
            conditions.append(Article.relevance >= f.min_relevance)
        if f.analyzed_only:
            conditions.append(Article.analysis_status == "done")
        if f.query:
            escaped = f.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            # ponytail: LIKE scan, fine below ~100k rows; move to FTS5 beyond that.
            conditions.append(
                or_(
                    *(
                        col.ilike(pattern, escape=LIKE_ESCAPE)
                        for col in (Article.title, Article.snippet, Article.summary)
                    )
                )
            )
        return conditions

    def list_articles(
        self, f: ArticleFilters, sort: str, limit: int, offset: int
    ) -> tuple[list[Article], int]:
        order = (
            (Article.relevance.desc().nulls_last(), PUBLISHED.desc())
            if sort == "relevance"
            else (PUBLISHED.desc(),)
        )
        where = self._conditions(f)
        with self._sessions() as s:
            total = s.scalar(select(func.count(Article.id)).where(*where))
            items = s.scalars(
                select(Article)
                .where(*where)
                .order_by(*order, Article.id.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(items), total or 0

    def list_sources(self) -> list[tuple[str, int]]:
        with self._sessions() as s:
            rows = s.execute(
                select(Article.source, func.count())
                .group_by(Article.source)
                .order_by(func.count().desc(), Article.source)
            )
            return [(name, count) for name, count in rows]

    def insights(self, days: int) -> dict[str, object]:
        since = utcnow() - timedelta(days=days)
        in_window = PUBLISHED >= since
        with self._sessions() as s:
            totals = s.execute(
                select(
                    func.count(),
                    func.count(case((Article.analysis_status == "done", 1))),
                    func.avg(Article.relevance),
                ).where(in_window)
            ).one()
            sentiment = dict(
                s.execute(
                    select(func.coalesce(Article.sentiment, "unanalyzed"), func.count())
                    .where(in_window)
                    .group_by(func.coalesce(Article.sentiment, "unanalyzed"))
                ).all()
            )
            histogram = dict(
                s.execute(
                    select(Article.relevance, func.count())
                    .where(in_window, Article.relevance.is_not(None))
                    .group_by(Article.relevance)
                ).all()
            )
            theme = func.json_each(Article.themes).table_valued("value").alias("theme")
            themes = s.execute(
                select(func.max(theme.c.value), func.count())
                .select_from(Article)
                .join(theme, true())
                .where(in_window)
                .group_by(func.lower(theme.c.value))
                .order_by(func.count().desc())
                .limit(15)
            ).all()
            sources = s.execute(
                select(Article.source, func.count(), func.avg(Article.relevance))
                .where(in_window)
                .group_by(Article.source)
                .order_by(func.count().desc(), Article.source)
                .limit(10)
            ).all()
            day = func.date(PUBLISHED)
            daily = s.execute(
                select(day, func.count()).where(in_window).group_by(day).order_by(day)
            ).all()
        total, analyzed, avg = totals
        return {
            "days": days,
            "total": total,
            "analyzed": analyzed,
            "avg_relevance": round(avg, 2) if avg is not None else None,
            "sentiment": {
                k: sentiment.get(k, 0) for k in ("positive", "neutral", "negative", "unanalyzed")
            },
            "relevance_histogram": [histogram.get(score, 0) for score in range(1, 11)],
            "top_themes": [{"name": n, "count": c} for n, c in themes],
            "top_sources": [
                {"name": n, "count": c, "avg_relevance": round(r, 2) if r is not None else None}
                for n, c, r in sources
            ],
            "daily": [{"date": d, "count": c} for d, c in daily],
        }
