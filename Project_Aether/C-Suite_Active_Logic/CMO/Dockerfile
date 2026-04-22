# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend logic
COPY backend/ ./backend/
# Copy frontend static assets
COPY frontend/ ./frontend/
# Copy config
COPY agent_config.json .

EXPOSE 5020

# Execute from the /app root to preserve relative pathing for volume mounts
CMD ["python", "backend/server.py"]
