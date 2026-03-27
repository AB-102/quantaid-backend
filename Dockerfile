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

# Flask runs on this port
EXPOSE 5000

# Run application via uv so the venv is activated
CMD ["uv", "run", "gunicorn", "app:app", "--workers", "4", "--bind", "0.0.0.0:5000", "--timeout", "120"]
