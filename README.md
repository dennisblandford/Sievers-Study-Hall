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

Optional macOS app-bundle tooling:

```bash
uv sync --group macos
```

Lint and format (configuration lives in `pyproject.toml`):

```bash
uv run ruff check
uv run ruff format
```

## Accounts

Accounts use a Mullvad-style account code instead of an email address and
password. Signing up creates a random UUID code that is shown once; save it,
because it is the only way to sign in. An email address is optional and is only
used to send the account code back if you lose it.

Existing databases are migrated automatically on startup: the old password
column is dropped and every user receives an account code. Existing email
addresses are kept as recovery aliases.

## Deploy on your own server

Requirements: Docker with the Compose plugin.

### 1. Configure

```bash
cp .env.example .env
```

Set at least `FLASK_SECRET_KEY` in `.env`. Generate a strong value with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Optional:

- `HF_TOKEN` enables AI-graded prompt exercises.
- `MAIL_USERNAME` / `MAIL_PASSWORD` enable recovery emails (the account code).

### 2. Start

```bash
docker compose up -d --build
```

Add `sudo` if your user is not in the `docker` group.

The app listens on `http://<server-ip>:8081`. To use a different host port,
edit `ports` in `compose.yaml`.

### 3. Put it behind HTTPS

Run the container behind any reverse proxy or TLS terminator (Caddy, nginx,
Traefik, a Cloudflare Tunnel, etc.) and forward `X-Forwarded-Proto`,
`X-Forwarded-For` and `Host`. Once HTTPS is in place, set
`SESSION_COOKIE_SECURE=1` in `.env` and restart.

### Configuration

| Variable | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Session signing key (set a strong value in production) |
| `DATABASE_URL` | SQLite location (Docker default: `/data/prod.db`) |
| `HF_TOKEN` | Enables AI-graded prompt exercises |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | Optional recovery email (account code) |
| `SESSION_COOKIE_SECURE` | Set to `1` when serving over HTTPS |
| `PORT` | Local Flask dev server only |

### Data and backups

Docker named volumes `data` (SQLite, WAL enabled) and `logs` (CSV analytics)
are created automatically and survive rebuilds.

Back up the database with:

```bash
docker compose cp web:/data/prod.db ./prod.db
```

To use host directories instead of named volumes, replace the `volumes` entries
in `compose.yaml` with:

```yaml
volumes:
  - ./instance:/data
  - ./logs:/app/logs
```

The container runs as UID `1000`, so make sure those directories are writable by
that UID:

```bash
mkdir -p instance logs
sudo chown -R 1000:1000 instance logs
```

### Operations

```bash
docker compose logs -f web   # follow logs
docker compose restart web   # restart the app
docker compose down          # stop
```

> Note: `HF_TOKEN` is required for AI-graded prompt exercises. Without it those
> exercises return a 503, while all other exercise types work normally.
