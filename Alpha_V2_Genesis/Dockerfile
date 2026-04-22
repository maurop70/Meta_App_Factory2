# Dockerfile
FROM python:3.10-slim
WORKDIR /app

# Install dependencies for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all local logic engines (Fragility, Strategy Ledger, Telemetry)
# Note: Alpha_Data/ and heavy artifacts are excluded via .dockerignore
COPY . .

# Explicitly exposed for Alpha UI Challenger Panels and Memory Engine
EXPOSE 5008

CMD ["python", "server.py"]
