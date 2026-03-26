FROM python:3.11-slim AS builder

# System deps needed to compile argon2-cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (this layer is cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Run as non-root user
RUN useradd -m appuser
USER appuser

# Copy app code
COPY --chown=appuser:appuser . .

# Flask runs on this port
EXPOSE 5000

# Run application
CMD ["gunicorn", "app:app", "--workers", "4", "--bind", "0.0.0.0:5000", "--timeout", "120"]
