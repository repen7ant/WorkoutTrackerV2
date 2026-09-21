FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# uv run по умолчанию досинхронизирует окружение в рантайме и тянет dev-группу.
# В контейнере это лишнее: образ уже собран из лок-файла. Переменные действуют
# и на CMD, и на command: в docker-compose.
ENV UV_NO_DEV=1 \
    UV_FROZEN=1

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache --no-dev

COPY . .

CMD ["uv", "run", "-m", "bot"]
