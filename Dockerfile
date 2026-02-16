FROM python:3.11-slim AS builder

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --no-dev --frozen

# --- runtime ---
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="duh" \
      org.opencontainers.image.description="Multi-model consensus engine" \
      org.opencontainers.image.source="https://github.com/msitarzewski/duh"

RUN groupadd --gid 1000 duh && \
    useradd --uid 1000 --gid duh --create-home duh && \
    mkdir -p /data && chown duh:duh /data

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src
COPY alembic.ini ./
COPY alembic/ alembic/
COPY docker/config.toml /app/config.toml

ENV PATH="/app/.venv/bin:$PATH"
ENV DUH_CONFIG="/app/config.toml"

VOLUME ["/data"]

USER duh

ENTRYPOINT ["duh"]
CMD ["--help"]
