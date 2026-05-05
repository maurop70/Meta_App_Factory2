FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Port 9000 internally
EXPOSE 9000

CMD ["uvicorn", "gateway_server:app", "--host", "0.0.0.0", "--port", "9000"]
