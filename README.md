# Sievers Study Hall

Interactive German grammar exercises built with Flask.

## Development

This project uses [uv](https://docs.astral.sh/uv/) and a standard
`pyproject.toml` (no `requirements.txt`).

```bash
# Create .venv, install the Python version and all dependencies
uv sync

# Run the test suite
uv run pytest

# Run the app locally (development database)
uv run --env-file .env python local.py

# Or serve the app with the Flask CLI
uv run --env-file .env flask --app app run --port 8080
```

Configuration is read from environment variables (`FLASK_SECRET_KEY`,
`DATABASE_URL`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `HF_TOKEN`, `PORT`,
`SESSION_COOKIE_SECURE`). Copy `.env.example` to `.env` and fill in the secrets
you need.

Optional macOS app-bundle tooling:

```bash
uv sync --group macos
```

Lint and format (configuration lives in `pyproject.toml`):

```bash
uv run ruff check
uv run ruff format
```

## Docker deployment

The app runs as a single gunicorn container on port `8081` (change the
published port in `compose.yaml` if needed).

```bash
docker compose up -d --build
```

Add `sudo` if your user is not in the `docker` group.

Runtime data is persisted in `./instance` (SQLite, WAL enabled) and `./logs`
(CSV analytics). Both are gitignored. The container healthcheck hits `/healthz`.

To serve over HTTPS, put the container behind any reverse proxy or TLS
terminator and forward `X-Forwarded-Proto`, `X-Forwarded-For` and `Host`.
Set `SESSION_COOKIE_SECURE=1` in `.env` when doing so.

> Note: `HF_TOKEN` is required for AI-graded prompt exercises. Without it those
> exercises return a 503, while all other exercise types work normally.
