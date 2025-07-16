# Production Dockerfile for BrainOps AI Ops Bot
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r brainops && useradd -r -g brainops brainops

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R brainops:brainops /app

# Switch to non-root user
USER brainops

# Environment variable for port (default 10000, can be overridden)
ENV PORT=10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE 10000

# Default command - run API server with dynamic port
CMD ["sh", "-c", "python bot.py serve --port ${PORT} --host 0.0.0.0"]