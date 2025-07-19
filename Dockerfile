# Production Dockerfile for BrainOps Backend
FROM python:3.12-slim

# Set working directory to root of project
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional packages
RUN pip install pyotp qrcode[pil] email-validator croniter opencv-python-headless boto3 anthropic pytesseract

# Copy entire project structure to maintain package hierarchy
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set Python path to include the app directory
ENV PYTHONPATH=/app

# Expose port (use Render's PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run production server with module path
CMD ["sh", "-c", "uvicorn apps.backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"]