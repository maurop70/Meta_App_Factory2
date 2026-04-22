# Dockerfile
FROM python:3.10-slim
WORKDIR /app

# Install dependencies first for layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy structure
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Explicitly expose port 5110 (as defined in Venture_Architect_Agent/backend/server.py)
EXPOSE 5110

# Execute from the /app root to preserve relative pathing for volume mounts
CMD ["python", "backend/server.py"]
