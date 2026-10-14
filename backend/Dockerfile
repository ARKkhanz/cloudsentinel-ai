# CloudSentinel AI — Backend Dockerfile
# Base: Official maintained Python 3.11 slim image
FROM python:3.11-slim

# Prevent generation of .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DATABASE_URL="sqlite:////app/backend/data/cloudsentinel.db"

# Set working directory to application root
WORKDIR /app

# Create dedicated non-root application group and user
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --no-create-home cloudsentinel

# Copy dependency specifications first to leverage Docker layer caching
COPY backend/requirements.txt /app/backend/requirements.txt

# Install runtime Python dependencies without caching wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source code into container
COPY backend/ /app/backend/

# Ensure SQLite data directory exists and set ownership for non-root execution
RUN mkdir -p /app/backend/data && \
    chown -R cloudsentinel:appgroup /app

# Switch to non-root user
USER cloudsentinel

# Expose internal FastAPI port
EXPOSE 8000

# Container healthcheck targeting GET /health using Python standard library
# (Avoids relying on curl/wget which are omitted in slim images)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').getcode() == 200 else 1)"

# Start Uvicorn with a single worker suitable for SQLite concurrency
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
