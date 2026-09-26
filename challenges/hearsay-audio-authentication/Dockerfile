# syntax=docker/dockerfile:1.7
# Build context: this directory (challenges/hearsay-audio-authentication).

ARG UV_VERSION=0.11.19

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM node:20-bookworm-slim AS frontends
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm ci --prefix frontend --no-audit --no-fund
COPY landing/package.json landing/package-lock.json landing/
RUN npm ci --prefix landing --no-audit --no-fund
COPY frontend/ frontend/
COPY landing/ landing/
RUN npm run build --prefix frontend && npm run build --prefix landing

FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

# Mirror the repository layout: modules resolve .env and reports/ relative to their own path.
ENV APP_ROOT=/opt/echotrace/challenges/hearsay-audio-authentication
ENV BACKEND_ROOT=${APP_ROOT}/backend \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR ${BACKEND_ROOT}
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY reports/ ${APP_ROOT}/reports/
RUN uv sync --frozen --no-dev \
    && rm -rf artifacts \
    && ln -s /data/artifacts artifacts

COPY --from=frontends /build/landing/dist /srv/static/landing
COPY --from=frontends /build/frontend/dist /srv/static/app
COPY deploy/entrypoint.sh /usr/local/bin/echotrace-entrypoint

RUN groupadd --system --gid 10001 echotrace \
    && useradd --system --uid 10001 --gid echotrace --home-dir /home/echotrace --create-home echotrace \
    && mkdir -p /data/artifacts /data/workspace /data/cache \
    && chown -R echotrace:echotrace /data \
    && chmod 0755 /usr/local/bin/echotrace-entrypoint

ENV PATH=${BACKEND_ROOT}/.venv/bin:${PATH} \
    HOME=/home/echotrace \
    HF_HOME=/data/cache/huggingface \
    ECHOTRACE_WORKSPACE=/data/workspace \
    ECHOTRACE_STATIC_ROOT=/srv/static

USER echotrace
VOLUME ["/data"]
EXPOSE 8000

# Long start period: first boot downloads the pinned NII checkpoint before uvicorn starts.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20m --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["/usr/local/bin/echotrace-entrypoint"]
