FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync

COPY src ./src

CMD ["uv", "run", "safie-api-mcp-server"]
