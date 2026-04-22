# Stage 1: Build React Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/resonance_ui
COPY resonance_ui/package*.json ./
RUN npm install
COPY resonance_ui/ ./
RUN npm run build

# Stage 2: Python Backend (Execution Engine)
FROM python:3.10-slim
WORKDIR /app

# Install dependencies for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly copies nerve_center.py and all root logic
COPY *.py ./
# Explicitly copies the local engines (dr_aris_engine.py and council_engine.py)
COPY Resonance_Engines/ ./Resonance_Engines/

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/resonance_ui/dist ./resonance_ui/dist

EXPOSE 5006

CMD ["python", "server.py"]
