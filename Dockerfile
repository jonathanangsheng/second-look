# Replay server: the built UI plus the read-only API over committed cards. No model credentials needed.

# Both Python stages must use the same image: the runtime reuses the builder's venv.
ARG PYTHON_IMAGE=python:3.12.15-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704

FROM node:24.22.1-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM ${PYTHON_IMAGE} AS app
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src src
# Editable install (uv's default): config.ROOT then resolves to /app, where the data below lives.
RUN uv sync --frozen --no-dev

# Runtime: the same base image, so the venv's python link still resolves; uv itself stays behind.
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY --from=app /app /app
COPY profiles profiles
COPY data data
COPY cards cards
COPY --from=web /app/web/dist web/dist
RUN useradd --no-create-home app
USER app
EXPOSE 8000
CMD [".venv/bin/uvicorn", "second_look.api:app", "--host", "0.0.0.0", "--port", "8000"]
