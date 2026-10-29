from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Engine,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC in SQLite and always hands back aware UTC datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to UTCDateTime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


SENTIMENTS = ("positive", "neutral", "negative")
ANALYSIS_STATUSES = ("pending", "done", "failed", "skipped")
RUN_STATUSES = ("running", "succeeded", "partial", "failed")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    phase: Mapped[str] = mapped_column(String(16), default="fetching")
    keywords: Mapped[list[str]] = mapped_column(JSON)
    max_results: Mapped[int] = mapped_column(Integer)
    analyze: Mapped[bool]
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fetched: Mapped[int] = mapped_column(default=0)
    new: Mapped[int] = mapped_column(default=0)
    to_analyze: Mapped[int] = mapped_column(default=0)
    analyzed: Mapped[int] = mapped_column(default=0)
    analysis_failed: Mapped[int] = mapped_column(default=0)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    # Human-readable problems that did not abort the run (one per line).
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="ck_runs_status"),
        # At most one running refresh, enforced by the database rather than a process lock.
        Index(
            "ux_runs_single_running", "status", unique=True, sqlite_where=text("status = 'running'")
        ),
    )


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))
    snippet: Mapped[str] = mapped_column(Text, default="")
    keyword: Mapped[str] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    first_run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))

    analysis_status: Mapped[str] = mapped_column(String(16), default="pending")
    summary: Mapped[str | None] = mapped_column(Text)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    sentiment: Mapped[str | None] = mapped_column(String(16))
    relevance: Mapped[int | None]
    analysis_error: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    model: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        CheckConstraint(f"analysis_status IN {ANALYSIS_STATUSES}", name="ck_articles_status"),
        CheckConstraint(
            f"sentiment IS NULL OR sentiment IN {SENTIMENTS}", name="ck_articles_sentiment"
        ),
        CheckConstraint(
            "relevance IS NULL OR relevance BETWEEN 1 AND 10", name="ck_articles_relevance"
        ),
        Index("ix_articles_published", text("coalesce(published_at, first_seen_at) DESC")),
        Index("ix_articles_relevance", "relevance"),
        Index("ix_articles_source", "source"),
    )


def make_engine(path: Path) -> Engine:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn: Any, _: Any) -> None:
        cur = dbapi_conn.cursor()
        # WAL lets the feed read while a refresh writes; busy_timeout absorbs brief write locks.
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def init_db(engine: Engine) -> sessionmaker[Session]:
    # ponytail: create_all covers a fresh v2 schema; add Alembic with the first schema change.
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
