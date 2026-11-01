# Copilot instructions

HR News Intelligence is a FastAPI + SQLite backend (`backend/app`) with a Vue 3 + TypeScript SPA (`frontend/src`).

- Backend: typed Python 3.12+, strict mypy, ruff. Routes in `api.py`, SQL in `store.py`, providers behind the `NewsSource` / `Analyzer` protocols, run orchestration in `pipeline.py`.
- Article text from search results is untrusted: never render it as HTML, never let it reach a prompt except as JSON data.
- API keys come from the environment only and must never be logged.
- Frontend: `<script setup lang="ts">`, no UI library; design tokens live in `src/styles.css`. Filters are URL state.
- Every change ships with tests: `backend/tests` (pytest, fakes over network) and `frontend/src/**/*.test.ts` (vitest).
