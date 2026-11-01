# HR News Intelligence

Find the HR news that matters to you. Each article comes with a one-line summary, its key themes, a sentiment, and a relevance score. Everything collected stays searchable.

- **Backend**: FastAPI, SQLite (WAL), SerpAPI news search, Google Gemini analysis with schema-constrained JSON output.
- **Frontend**: Vue 3 + TypeScript (Vite). There is no UI framework. The app works in light and dark mode and is keyboard- and screen-reader-friendly.
- **Docs**: [product brief](docs/PRODUCT.md) · [architecture diagram](docs/architecture.html) (open it in a browser) · [security notes](SECURITY.md)

## Quick start

You need Python 3.12+ with [uv](https://docs.astral.sh/uv/), and Node 22+.

```bash
cd backend
cp .env.example .env          # add SERPAPI_KEY and GEMINI_API_KEY
uv sync                       # creates backend/.venv; nothing is installed globally
```

```bash
cd frontend
npm ci
npm run build                 # FastAPI serves frontend/dist
```

```bash
cd backend
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. For frontend development with hot reload, also run `npm run dev` in `frontend/` and open http://127.0.0.1:5173. Vite proxies `/api` to the backend.

| Variable | Required | Purpose |
|---|---|---|
| `SERPAPI_KEY` | yes | News search ([serpapi.com](https://serpapi.com/)) |
| `GEMINI_API_KEY` | for analysis | Summaries, themes, sentiment, relevance ([Google AI Studio](https://aistudio.google.com/)) |
| `GEMINI_MODEL` | no | Defaults to the `gemini-flash-latest` alias. Pin a specific model ID if you need reproducible output |
| `DATABASE_PATH` | no | Defaults to `backend/data/hr_news.db` |
| `ALLOWED_HOSTS` | no | Host-header allow-list (JSON list). Add your hostname if you put the app behind a proxy |

If `GEMINI_API_KEY` is missing, refreshes still store articles, marked "Not analyzed". If `SERPAPI_KEY` is missing, the UI explains how to add it.

## How a refresh works

1. `POST /api/runs` records a run. A partial unique index guarantees only one refresh runs at a time (a second request gets `409`).
2. Keywords are searched concurrently. Results are deduplicated by canonical URL, and tracking parameters are stripped. Only `http(s)` links are accepted.
3. New URLs are inserted. Known URLs are touched. An article that was already analyzed is never sent to Gemini again.
4. Articles still needing analysis go to Gemini in batches (8 per call, 2 calls in flight). The SDK retries 429 and 5xx responses with backoff. Output is validated and clamped. An article the model skipped is marked `failed` and retried on the next refresh that finds it.
5. The run record keeps counts, warnings, and token usage. The UI polls it for progress.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Which providers are configured (never the keys) and the model |
| POST | `/api/runs` | `{keywords: string[1..10], max_results: 5..50, analyze: bool}` → `202` |
| GET | `/api/runs`, `/api/runs/{id}` | Run status and progress |
| GET | `/api/articles` | `sentiment`, `source` (repeatable), `min_relevance`, `q`, `sort=newest\|relevance`, `limit`, `offset` |
| GET | `/api/sources` | Source names with counts, for filters |
| GET | `/api/insights?days=30` | Sentiment mix, relevance histogram, top themes and sources, daily volume |

Interactive docs are at `/docs`.

## Quality gates

```bash
cd backend && uv sync --all-groups && uv run ruff check . && uv run mypy app && uv run pytest
```

```bash
cd frontend && npm test && npm run build
```

`pytest` covers the API, the providers (parsing, sanitizing, and failure modes, all faked at the network edge), and browser end-to-end flows. The browser tests drive the built SPA in Chromium through the real API with deterministic demo providers. They are skipped if `frontend/dist` is missing. CI runs all of the above.

To evaluate the analysis prompt against labeled cases (needs `GEMINI_API_KEY`; spends a few cents):

```bash
cd backend && uv run python -m evals.run_eval
```

The eval reports schema coverage, sentiment accuracy, relevance-band accuracy, and whether a prompt-injection case was resisted. It exits non-zero below its floors.

To preview the UI without API keys:

```bash
cd backend && uv run python -m tests.e2e.demo_server --port 8001 --db /tmp/demo.db
```

## Project layout

```
backend/app/      config, db (models), store (SQL), news (SerpAPI), analysis (Gemini), pipeline (runs), api, main
backend/tests/    API + provider tests; e2e/ browser tests and demo server
backend/evals/    labeled prompt-evaluation cases
frontend/src/     lib/ (API client, URL filter state, formatting), components/, views/ (Feed, Insights)
docs/             product brief, architecture diagram source (archify JSON) and render
```

## License

No license file has been chosen yet. The previous README referred to an MIT `LICENSE` file that never existed in the repository. Add one before you redistribute.
