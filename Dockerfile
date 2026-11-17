FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

# venv ссылается на python базового образа: обе стадии на одном образе,
# и uv не должен скачивать свой python
RUN uv sync --frozen --no-cache --no-dev --no-python-downloads


FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "bot"]
