# ============================================================
# LexGuard AI — FastAPI Backend Dockerfile
# Optimized for AWS EC2 t3.medium (2 vCPU, 4GB RAM)
# Region: ap-south-1 (Mumbai)
# ============================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

# Set working directory
WORKDIR /app

# Install system dependencies (for packages that compile C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    cmake \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY dpdp_knowledge_base.py .
COPY rag_engine.py .
COPY test_gemini.py .
COPY mock_server.py .

# Create a non-root user for security (optional but recommended)
# For EC2 single-container setups we run as root for simplicity,
# but in production consider: RUN useradd -m -u 1000 appuser && chown -R appuser /app

# Expose the FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run uvicorn with a single worker (t3.medium has 2 vCPUs; you can scale to 2 workers if needed)
# Using --host 0.0.0.0 to accept external connections
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
