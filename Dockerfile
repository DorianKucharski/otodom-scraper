# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# uv tuning: compile bytecode for faster startup, copy (not link) out of the
# cache mount, and don't fetch a standalone interpreter (the image ships one).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached layer) from just the lockfile + manifest.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy the application source.
COPY . .

# Run inside the project's virtual environment.
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py"]
