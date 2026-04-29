# Stage 1: Fetch Litestream
FROM alpine:latest as litestream_builder
ADD https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.tar.gz /tmp/litestream.tar.gz
RUN tar -C /usr/local/bin -xzf /tmp/litestream.tar.gz

# Stage 2: Backend Container
FROM python:3.12-slim
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y gcc sqlite3 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Inject Litestream
COPY --from=litestream_builder /usr/local/bin/litestream /usr/local/bin/litestream
COPY litestream.yml /etc/litestream.yml

# Privilege Dropping & Volumes
RUN useradd -m appuser && \
    mkdir -p /app/data /app/logs && \
    chown -R appuser:appuser /app /etc/litestream.yml

COPY . /app
RUN chown -R appuser:appuser /app

USER appuser
VOLUME /app/data
VOLUME /app/logs

EXPOSE 8000

# Litestream acts as the PID 1 supervisor
CMD ["litestream", "replicate", "-config", "/etc/litestream.yml", "-exec", "gunicorn", "maintenance_backend:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
