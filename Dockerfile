# Multi-stage Dockerfile for Railway deployment with uv
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.13-slim

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

# Start the combined Flask/MCP service; serve.py reads the environment-specific config.
CMD ["python", "serve.py"]
