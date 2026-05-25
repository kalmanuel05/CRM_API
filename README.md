# CRM Data Cleaner API

FastAPI service that normalizes CRM contact rows (email, phone, names), flags duplicates, and exports HubSpot / Salesforce / Zoho-ready CSV columns.

## Quick start (local)

```bash
./scripts/setup.sh    # venv, deps, copy .env.example → .env
./scripts/dev.sh      # http://127.0.0.1:8000
```

Or with Make:

```bash
make setup && make dev
```

- **Health:** `GET http://127.0.0.1:8000/health`
- **OpenAPI:** http://127.0.0.1:8000/docs
- **Postman:** import `postman_collection.json` (default `apiKey` = `sk_free_test`)

## Environment

Copy `.env.example` to `.env`. Minimum for authenticated API calls:

```env
CRM_AUTH_DISABLED=false
CRM_API_KEYS=sk_free_test:free
```

Postman / curl header:

```http
X-API-Key: sk_free_test
```

| Variable | Purpose |
|----------|---------|
| `CRM_AUTH_DISABLED` | `true` skips API keys (local dev only) |
| `CRM_API_KEYS` | Comma-separated `key:tier` (`free`, `starter`, `growth`, `pro`) |
| `CRM_USAGE_LOG_PATH` | JSONL usage log (default `logs/usage.jsonl`) |
| `CRM_MAX_JSON_BYTES` | Max JSON body for `/v1/clean` (default 10 MiB) |
| `CRM_MAX_CSV_BYTES` | Max CSV upload for `/v1/clean/csv` (default 5 MiB) |
| `CRM_DIAGNOSTICS_SECRET` | Enables `GET /v1/diagnostics/recent-errors` |
| `CRM_DIAGNOSTICS_OPENAPI` | `true` shows diagnostics route in `/docs` |
| `CRM_ERROR_LOG_PATH` | JSONL unhandled-error log (default `logs/errors.jsonl`) |
| `RAPIDAPI_PROXY_SECRET` | RapidAPI proxy auth (production on RapidAPI only) |

`.env` is loaded automatically on startup (`python-dotenv`). `logs/` is created when writing usage or error logs.

## Tests

```bash
make test
# or
.venv/bin/pytest -q
```

Tests use `sk_test_free:free` via `tests/conftest.py` (no local `.env` required).

## Deploy (Render)

`render.yaml` is included. In the Render dashboard, set at least:

- `CRM_AUTH_DISABLED=false`
- `CRM_API_KEYS` — production keys (secret)

Optional: usage/diagnostics paths and byte limits (see `.env.example`).

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Project layout

```
app/           # FastAPI app
tests/         # pytest suite
docs/          # RapidAPI listing copy
logs/          # usage.jsonl / errors.jsonl (gitignored)
scripts/       # setup.sh, dev.sh
```
