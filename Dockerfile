# Stage 1: Base Python Backend
FROM python:3.10-slim as backend
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "5000"]

