"""Serves the real app with deterministic fake providers, for browser tests and UI review.

Run from backend/: .venv/bin/python -m tests.e2e.demo_server --port 8001 --db /tmp/demo.db
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn

from app.analysis import ArticleAnalysis, ArticleInput, BatchResult
from app.config import Settings
from app.main import create_app
from app.news import FetchedArticle

NOW = datetime.now(UTC)
STORIES = [
    (
        "Pay transparency law takes effect, requiring salary ranges in job ads",
        "HR Dive",
        3,
        "positive",
        9,
        ["Pay Transparency", "Employment Law", "Recruiting"],
    ),
    (
        "Retailer lays off 4,000 corporate staff in restructuring",
        "Reuters",
        7,
        "negative",
        7,
        ["Layoffs", "Restructuring"],
    ),
    (
        "Survey: employee engagement climbs for third straight quarter",
        "Gallup",
        20,
        "positive",
        8,
        ["Employee Engagement", "Workforce Data"],
    ),
    (
        "Labor department finalizes overtime threshold update",
        "SHRM",
        30,
        "neutral",
        9,
        ["Overtime", "Employment Law", "Compensation"],
    ),
    (
        "How recruiters are using AI screening tools — and where it goes wrong",
        "Wired",
        46,
        "neutral",
        7,
        ["AI in Recruiting", "Recruiting", "Bias"],
    ),
    (
        "Four-day week pilot reports lower burnout, steady output",
        "The Guardian",
        52,
        "positive",
        7,
        ["Four-Day Week", "Wellbeing"],
    ),
    (
        "Court pauses noncompete ban, leaving employers in limbo",
        "Bloomberg Law",
        70,
        "neutral",
        8,
        ["Noncompetes", "Employment Law"],
    ),
    (
        "Return-to-office mandates linked to higher attrition among senior staff",
        "HR Dive",
        96,
        "negative",
        8,
        ["Return to Office", "Attrition"],
    ),
    (
        "Benefits costs set to rise 7% next year, insurers say",
        "SHRM",
        120,
        "negative",
        8,
        ["Benefits", "Compensation"],
    ),
    (
        "Quarterly earnings beat expectations at regional bank",
        "MarketWatch",
        140,
        "neutral",
        2,
        ["Earnings"],
    ),
]


class DemoNews:
    async def search(self, keyword: str, limit: int) -> list[FetchedArticle]:
        await asyncio.sleep(0.4)
        offset = sum(map(ord, keyword)) % 3
        picked = STORIES[offset:] + STORIES[:offset]
        return [
            FetchedArticle(
                url=f"https://news.example/{title.lower().replace(' ', '-')[:60]}",
                title=title,
                source=source,
                snippet=f"{title}. Coverage on what it means for HR teams.",
                published_at=NOW - timedelta(hours=hours),
            )
            for title, source, hours, *_ in picked[:limit]
        ]


class DemoAnalyzer:
    model = "demo-model"

    async def analyze(self, batch: list[ArticleInput]) -> BatchResult:
        await asyncio.sleep(0.5)
        by_title = {s[0]: s for s in STORIES}
        result = BatchResult(prompt_tokens=180 * len(batch), output_tokens=60 * len(batch))
        for a in batch:
            _, _, _, sentiment, relevance, themes = by_title[a.title]
            result.analyses[a.id] = ArticleAnalysis(
                id=a.id,
                summary=f"{a.title.split(',')[0]}; HR teams should review the impact.",
                themes=themes,
                sentiment=sentiment,
                relevance=relevance,
            )
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings(
        database_path=args.db,
        serpapi_key=None,
        gemini_api_key=None,
        gemini_model="demo-model",
        analysis_batch_size=4,
    )
    app = create_app(settings, providers=(DemoNews(), DemoAnalyzer()))
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
