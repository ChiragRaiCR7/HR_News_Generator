# HR News Intelligence — Product Brief

## Problem

HR practitioners need a short, trustworthy read on what changed in their field this week.
General news search returns duplicates, stale items, and irrelevant hits, and it does not
say *why* an item matters. The original Streamlit prototype proved the idea (SerpAPI search +
Gemini summaries) but kept nothing between refreshes, re-paid for every search and analysis,
and crashed when AI analysis was turned off.

## Users and jobs to be done

| Persona | Job | What "done" looks like |
|---|---|---|
| HR business partner | "Show me what happened this week that matters to me." | A ranked feed with one-line summaries, sentiment, and a relevance score. Duplicates removed. |
| Talent-acquisition lead | "Track the topics I care about." | Keyword-driven refresh. Results accumulate in history, so earlier finds stay searchable. |
| HR leader / CHRO | "Spot the trend, not the article." | Insights: theme frequency, sentiment mix, source mix, and volume over time. |
| Any user | "Find that article I saw on Tuesday." | Full-history text search and filters that persist in the URL. |

## Scope (v2)

1. **Refresh**: comma-separated keywords, 5–50 results, AI analysis on/off. Runs in the background with live progress. Only one refresh runs at a time.
2. **Persistence (SQLite)**: articles are deduplicated by URL. Each article's analysis is stored once and never paid for twice. Every refresh run is recorded with counts, timings, and errors.
3. **AI analysis (Gemini)**: schema-constrained JSON returns a summary, 1–5 themes, sentiment, and relevance (1–10). Articles are analyzed in batches with bounded retries. A failed analysis is retried on the next refresh that sees the article.
4. **Feed**: filter by sentiment, minimum relevance, source, and text search. Sort by newest or most relevant. Pages are loaded incrementally. Filter state is kept in the URL.
5. **Insights**: sentiment distribution, relevance histogram, top themes, top sources, and articles per day, over a 7/30/90-day window.
6. **Operational clarity**: a health endpoint reports which API keys are configured (never their values). The UI explains what is missing instead of failing silently.

## Non-goals (v2)

- Multi-user accounts and auth. This is a local, single-user tool that binds to `127.0.0.1` by default. See `SECURITY.md`.
- Scheduled background refresh. The old "updated every 6 hours" footer was never true. Manual refresh avoids spending API credits when nobody is reading.
- Multiple LLM providers. Gemini stays as the provider. The model ID is configurable because model IDs are retired frequently.
- Full-text index (FTS5). A `LIKE` scan is enough below roughly 100k articles.

## Acceptance criteria

- A refresh with AI analysis off succeeds and the articles appear in the feed as "Not analyzed". The legacy app crashed here with `KeyError: 'sentiment'`.
- Running the same refresh twice inserts no duplicates and makes no second analysis call for an already-analyzed article.
- A second refresh request while one is running returns `409`.
- Missing `SERPAPI_KEY` returns a clear `503` with remediation text. Missing `GEMINI_API_KEY` still stores articles, unanalyzed.
- Model output is validated: sentiment is an enum, relevance is clamped to 1–10, themes are capped at 5, and length limits apply. Malformed output marks only the affected articles as failed.
- The feed and insights are keyboard-operable, readable in light and dark themes, and usable at a 360 px width.
- Backend tests, frontend type-check and unit tests, and a browser end-to-end run all pass in CI.

## Legacy defects fixed by this rewrite

| Defect in the Streamlit app | Where | Resolution |
|---|---|---|
| Turning AI off crashes the page (`df['sentiment']` is missing) | `app.py:57` | Unanalyzed articles are first-class (`analysis_status = 'skipped'`) |
| News-tab results carry `source` as a string, so `.get('name')` raised and every keyword search failed (zero articles). Reproduced with a stubbed payload; the live payload shape was not re-verified | `news_fetcher.py:52` | Both string and object shapes are accepted (`tests/test_providers.py`) |
| Every refresh re-fetches and re-analyzes everything | `app.py:41-51` | URL dedup plus a stored per-article analysis |
| One Gemini call per article, run serially | `app.py:47-49` | Batched calls with bounded concurrency |
| JSON pulled out of free text with a regex | `content_processor.py:54` | Schema-constrained output, validated with Pydantic |
| Relative dates collapsed to "Today / This week" | `news_fetcher.py:71` | Converted to absolute UTC timestamps |
| Per-keyword quota divided by a count that includes empty keywords | `news_fetcher.py:32` | Keywords are normalized and deduplicated first |
| Retired model `gemini-1.5-flash` on the deprecated `google-generativeai` SDK | `content_processor.py:18` | `google-genai` SDK with a configurable model |
| False "Updated every 6 hours" claim | `app.py:151` | Removed |
| Merge-conflict marker in the README | `README.md:99` | README rewritten |
