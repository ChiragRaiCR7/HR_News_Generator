"""API request and response contracts."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Sentiment = Literal["positive", "neutral", "negative"]
MAX_KEYWORDS = 10


class RefreshRequest(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=MAX_KEYWORDS)
    max_results: int = Field(default=15, ge=5, le=50)
    analyze: bool = True

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        """Trims, collapses whitespace, and drops empty or case-insensitive duplicate keywords."""
        seen: dict[str, str] = {}
        for raw in value:
            keyword = " ".join(raw.split())
            if len(keyword) > 100:
                raise ValueError("each keyword must be at most 100 characters")
            if keyword:
                seen.setdefault(keyword.lower(), keyword)
        if not seen:
            raise ValueError("at least one non-empty keyword is required")
        return list(seen.values())


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["running", "succeeded", "partial", "failed"]
    phase: Literal["fetching", "analyzing", "done"]
    keywords: list[str]
    max_results: int
    analyze: bool
    started_at: datetime
    finished_at: datetime | None
    fetched: int
    new: int
    to_analyze: int
    analyzed: int
    analysis_failed: int
    prompt_tokens: int
    output_tokens: int
    warnings: list[str]
    error: str | None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    source: str
    snippet: str
    keyword: str
    published_at: datetime | None
    first_seen_at: datetime
    analysis_status: Literal["pending", "done", "failed", "skipped"]
    summary: str | None
    themes: list[str]
    sentiment: Sentiment | None
    relevance: int | None
    analysis_error: str | None


class ArticlePage(BaseModel):
    items: list[ArticleOut]
    total: int
    limit: int
    offset: int


class NameCount(BaseModel):
    name: str
    count: int


class SourceStat(NameCount):
    avg_relevance: float | None


class DayCount(BaseModel):
    date: date
    count: int


class SentimentCounts(BaseModel):
    positive: int
    neutral: int
    negative: int
    unanalyzed: int


class Insights(BaseModel):
    days: int
    total: int
    analyzed: int
    avg_relevance: float | None
    sentiment: SentimentCounts
    relevance_histogram: Annotated[list[int], Field(min_length=10, max_length=10)]
    top_themes: list[NameCount]
    top_sources: list[SourceStat]
    daily: list[DayCount]


class Health(BaseModel):
    status: Literal["ok"]
    version: str
    serpapi_configured: bool
    gemini_configured: bool
    model: str
