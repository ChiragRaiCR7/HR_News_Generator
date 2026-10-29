"""SerpAPI news search: fetches Google News-tab results and normalizes them."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

log = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"
# SerpAPI answers an empty search with this error string instead of an empty list.
NO_RESULTS_MARKER = "hasn't returned any results"
TRACKING_PARAM = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid)$", re.IGNORECASE)
RELATIVE_DATE = re.compile(r"(\d+)\s+(minute|min|hour|day|week|month|year)s?\s+ago", re.I)
RELATIVE_UNITS = {
    "minute": timedelta(minutes=1),
    "min": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),
    "year": timedelta(days=365),
}
ABSOLUTE_DATE_FORMATS = ("%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%m/%d/%Y")


class NewsSourceError(Exception):
    """The provider rejected the search (bad key, quota, outage)."""


@dataclass(frozen=True, slots=True)
class FetchedArticle:
    url: str
    title: str
    source: str
    snippet: str
    published_at: datetime | None


class NewsSource(Protocol):
    async def search(self, keyword: str, limit: int) -> list[FetchedArticle]: ...


def canonical_url(raw: str) -> str | None:
    """Normalizes a result link for deduplication; rejects anything but http(s)."""
    try:
        parts = urlsplit(raw.strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not TRACKING_PARAM.match(k)
        ]
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def parse_date(raw: str | None, now: datetime) -> datetime | None:
    """Turns '3 hours ago' or 'Oct 27, 2026' into an absolute UTC timestamp."""
    if not raw:
        return None
    raw = raw.strip()
    if m := RELATIVE_DATE.search(raw):
        return now - int(m.group(1)) * RELATIVE_UNITS[m.group(2).lower()]
    for fmt in ABSOLUTE_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _source_name(item: dict[str, Any]) -> str:
    # The news tab returns a plain string; the google_news engine returns {"name": ...}.
    source = item.get("source")
    name = source.get("name") if isinstance(source, dict) else source
    return re.sub(r"\s+", " ", str(name or "")).strip(" ·|-") or "Unknown"


def parse_results(payload: dict[str, Any], now: datetime) -> list[FetchedArticle]:
    articles = []
    for item in payload.get("news_results", []):
        url = canonical_url(str(item.get("link", "")))
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        articles.append(
            FetchedArticle(
                url=url,
                title=title[:500],
                source=_source_name(item)[:200],
                snippet=str(item.get("snippet") or "").strip()[:2000],
                published_at=parse_date(item.get("date"), now),
            )
        )
    return articles


class SerpApiNews:
    """NewsSource backed by SerpAPI's Google search with the news tab (tbm=nws)."""

    def __init__(self, api_key: str, client: httpx.AsyncClient) -> None:
        self._api_key = api_key
        self._client = client

    async def search(self, keyword: str, limit: int) -> list[FetchedArticle]:
        params: dict[str, str | int] = {
            "engine": "google",
            "tbm": "nws",
            "q": keyword,
            "num": limit,
            "hl": "en",
            "gl": "us",
            "api_key": self._api_key,
        }
        try:
            resp = await self._client.get(SERPAPI_URL, params=params)
        except httpx.HTTPError as exc:
            # Never log the request URL: it carries the API key.
            raise NewsSourceError(f"network error: {type(exc).__name__}") from None
        try:
            payload = resp.json()
        except ValueError:
            raise NewsSourceError(f"HTTP {resp.status_code}, non-JSON body") from None
        if error := payload.get("error"):
            if NO_RESULTS_MARKER in error:
                return []
            raise NewsSourceError(str(error)[:300])
        if resp.status_code >= 400:
            raise NewsSourceError(f"HTTP {resp.status_code}")
        articles = parse_results(payload, datetime.now(UTC))
        log.info("serpapi keyword=%r results=%d", keyword, len(articles))
        return articles[:limit]
