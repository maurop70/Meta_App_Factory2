# ── Delegate AI Beta-Agreement Vault — Backend Dockerfile ──
FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY config.json .
COPY bridge.py .

# Create data directory
RUN mkdir -p /app/vault_data

EXPOSE 5007

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5007/health')" || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5007"]
