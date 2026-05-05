FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

EXPOSE 8000

# Start Uvicorn, bind to 0.0.0.0
CMD ["uvicorn", "maintenance_backend:app", "--host", "0.0.0.0", "--port", "8000"]
