# Chapter 35: the Studio backend and worker, containerized, on the
# same server Chapter 15/16's SIP stack already runs on. This image
# serves both `studio_api.py` (uvicorn) and `dynamic_agent.py` (the
# worker); which one a given container runs is the compose file's
# `command`, not a build-time choice.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
