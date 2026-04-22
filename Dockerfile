FROM python:3.10-slim

# System dependencies for native Python operations
RUN apt-get update && apt-get install -y gcc git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install uvicorn

# Bake core files into the image (overridden by bind mount in dev, but architecturally sound)
COPY . .

# Expose the central factory hub port
EXPOSE 5000

# Execute the core API entry point
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "5000"]
