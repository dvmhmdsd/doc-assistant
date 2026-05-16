# syntax=docker/dockerfile:1.6
#
# Multi-stage build for doc-assistant.
#   Stage 1 (frontend-builder): builds the React + Tailwind SPA (feature 002)
#     into static assets under /frontend/dist.
#   Stage 2 (runtime): Python 3.11-slim running the FastAPI app, which serves
#     /frontend/dist at "/" and exposes the API on the same origin.
#
# Single-image, single-process production target. The test runner ships in
# the same image:
#   docker compose run --rm app pytest

# ---------- Stage 1: build the SPA ----------
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /frontend

# Install deps first for cache reuse.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Build the SPA.
COPY frontend/ ./
RUN npm run build
# Expected output: /frontend/dist (Vite default).

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for PyMuPDF and sentence-transformers (libgomp). Keep minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend deps including dev extras so pytest/ruff/mypy run inside
# this same image via `docker compose run --rm app ...`.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Backend source + tests.
COPY src/ ./src/
COPY tests/ ./tests/

# Static SPA assets from the frontend stage.
COPY --from=frontend-builder /frontend/dist /app/frontend_dist

EXPOSE 8000

# Non-root user.
RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
