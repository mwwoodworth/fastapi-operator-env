# Dockerfile for BrainOps FastAPI Backend
# Production-ready build with proper working directory and health checks

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/apps/backend \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory to where our code will live
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire FastAPI application
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p logs data temp && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE $PORT

# Start the FastAPI application with Uvicorn
# Using apps.backend.main:app because main.py is in apps/backend/
# Use shell form to enable PORT variable expansion
CMD uvicorn apps.backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2