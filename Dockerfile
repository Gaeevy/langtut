# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for Railway deployment
# Uses uv for fast, reliable dependency management

# Stage 1: Build dependencies
FROM python:3.11.10-slim AS builder

# Install uv - the fast Python package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency specification files
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv
# --frozen: Use exact versions from uv.lock (no resolution)
# --no-dev: Skip development dependencies
RUN uv sync --frozen --no-dev

# Stage 2: Production runtime
FROM python:3.11.10-slim

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Create data directory for database volume mount
RUN mkdir -p /app/data

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Expose the application port
EXPOSE 8080

# Run gunicorn with production-optimized settings for Railway Hobby plan
# Use shell form to properly expand $PORT environment variable
# Single worker to stay within 512MB RAM limit
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile - --log-level info app:app

