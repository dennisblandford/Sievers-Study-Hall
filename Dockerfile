# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL="sqlite:////data/prod.db"

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code (datasets included).
COPY app.py ./
COPY data ./data
COPY users ./users
COPY webapp ./webapp

# Run as an unprivileged user; the SQLite DB and CSV logs live on mounted volumes.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data /app/logs \
    && chown -R app:app /data /app/logs
USER app

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/healthz')"]

CMD ["gunicorn", \
     "--bind", "0.0.0.0:8081", \
     "--worker-class", "gthread", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
