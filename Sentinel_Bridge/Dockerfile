# Dockerfile
FROM python:3.10-slim
WORKDIR /app

# Install dependencies for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly copy execution logic, routing rules, and the UI
COPY *.py ./
COPY *.json ./
COPY dashboard.html ./

# Expose global routing hub port
EXPOSE 5009

CMD ["python", "sentinel_server.py"]
