# Multi-stage Dockerfile for Railway deployment with uv
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv .venv

# Copy application code
COPY . .

# Create data directory for volume mount
RUN mkdir -p /app/data

# Set Python path and disable buffering
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Start application
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 1 \
    --access-logfile - \
    --error-logfile -
