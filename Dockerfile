# Replay server: the built UI plus the read-only API over committed cards. No model credentials needed.

FROM node:24.22.1-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS app
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
FROM python:3.12-slim
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
