FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies first (this layer is cached unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable --no-install-project

# Run as non-root user
RUN useradd -m appuser
USER appuser

# Copy app code
COPY --chown=appuser:appuser . .

EXPOSE 8000

# --no-sync: the image's environment is already built without dev dependencies; a sync at startup would try
# to install them as appuser and fail
CMD ["uv", "run", "--no-sync", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
