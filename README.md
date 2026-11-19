# Sievers Study Hall

Any question? https://substack.com/home/post/p-165326616

Any other question? sieversstudyhall@gmail.com

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

# Or serve the production-style entrypoint with the Flask CLI
uv run --env-file .env flask --app app run --port 8080
```

Configuration is read from environment variables (`FLASK_SECRET_KEY`,
`MAIL_USERNAME`, `MAIL_PASSWORD`, `HF_TOKEN`, `PORT`). Copy `.env.example` to
`.env` and fill in the secrets you need.

Optional macOS app-bundle tooling:

```bash
uv sync --group macos
```

Lint and format (configuration lives in `pyproject.toml`):

```bash
uv run ruff check
uv run ruff format
```
