# syntax=docker/dockerfile:1.6
#
# Backend-only build (Phase 3 in-flight, feature 002 frontend not yet
# scaffolded). When the React SPA lands under `frontend/`, restore the
# multi-stage build: a Node 20 `frontend-builder` stage that runs
# `npm ci && npm run build`, then `COPY --from=frontend-builder
# /frontend/dist /app/frontend_dist` here. The runtime is otherwise
# identical to what production will use.
#
# Single-image. Tests ship in this image too:
#   docker compose run --rm app pytest

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for PyMuPDF + sentence-transformers (libgomp).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend deps including dev extras so pytest/ruff/mypy run inside
# this image via `docker compose run --rm app ...`.
#
# Torch is pinned to the CPU wheel index BEFORE installing the rest, so
# sentence-transformers' transitive `torch` requirement is already
# satisfied with the CPU build. Without this, pip resolves the default
# CUDA-bundled torch and pulls ~2 GB of nvidia-* wheels that are dead
# weight on Apple Silicon / CPU-only hosts and a frequent build-timeout
# source.
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -e ".[dev]"

# Backend source + tests.
COPY src/ ./src/
COPY tests/ ./tests/

# Entrypoint script needs to run as root to chown the (root-mounted)
# named volumes before dropping to the `app` user via runuser.
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Non-root user (entrypoint drops to this via runuser).
RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /app

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
