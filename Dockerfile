# --- frontend build ---
FROM node:22-slim AS frontend

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# --- python build ---
FROM python:3.11-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --no-dev --frozen --no-editable

# --- runtime ---
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="duh" \
      org.opencontainers.image.description="Multi-model consensus engine" \
      org.opencontainers.image.source="https://github.com/msitarzewski/duh"

RUN groupadd --gid 1000 duh && \
    useradd --uid 1000 --gid duh --create-home duh && \
    mkdir -p /data && chown duh:duh /data

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=frontend /web/dist /app/web/dist
COPY alembic.ini ./
COPY alembic/ alembic/
COPY docker/config.toml /app/config.toml

ENV PATH="/app/.venv/bin:$PATH"
ENV DUH_CONFIG="/app/config.toml"

VOLUME ["/data"]
EXPOSE 8080

USER duh

ENTRYPOINT ["duh"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
