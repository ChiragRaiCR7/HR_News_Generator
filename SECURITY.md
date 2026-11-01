# Security notes

HR News Intelligence is a **single-user, local tool**. It has no accounts or authentication, and it binds to `127.0.0.1` by default.

## Controls in place

| Threat | Control |
|---|---|
| API keys leaking through logs | Keys are read from the environment as `SecretStr`. The `httpx` logger is raised to WARNING because SerpAPI URLs carry the key. Provider errors never echo the request URL. |
| Malicious links in search results (`javascript:`, `data:`) | Only `http(s)` URLs are stored (`news.canonical_url`). The frontend re-checks every link with `safeHref` before binding it. |
| XSS through titles, snippets, or model output | Vue text interpolation only; there is no `v-html`. A strict CSP (`script-src 'self'`, no inline scripts) is sent on every response. |
| Prompt injection in article text | Articles reach Gemini only as JSON data, under a system instruction that says to ignore embedded instructions. Output is schema-constrained and clamped. Unknown ids are dropped. The model has no tools and cannot trigger side effects. `evals/cases.jsonl` contains an injection case. |
| DNS rebinding / cross-site requests to the local server | `TrustedHostMiddleware` restricts Host headers. There is no CORS middleware, so a cross-origin JSON POST fails preflight. A `text/plain` body is rejected with a `422`. |
| Paid-API abuse | One refresh at a time (enforced by the database). At most 10 keywords and 50 results per run. Retries are bounded. |
| SQL injection | All SQL goes through SQLAlchemy with bound parameters. `LIKE` wildcards in search are escaped. |
| Clickjacking / referrer leakage | `frame-ancestors 'none'`, `Referrer-Policy: no-referrer`, `rel="noopener noreferrer"` on outbound links. |

## Exposing it beyond localhost

There is no authentication. Anyone who can reach the server can read the stored articles and start refreshes that spend your SerpAPI and Gemini quota. If you deploy it to a shared host:

1. Put it behind an authenticating reverse proxy (SSO or basic auth over TLS).
2. Add the public hostname to `ALLOWED_HOSTS`.
3. Run a single worker. SQLite and the in-process refresh task assume one process.

## Reporting

Report suspected vulnerabilities privately to the repository owner rather than in a public issue.
