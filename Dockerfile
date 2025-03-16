# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/ .
RUN npm install && npm run build

# Stage 2: Python backend
FROM python:3.10-slim  # Match Azure's Python version
WORKDIR /app

# Install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Copy built frontend assets
COPY --from=frontend-builder /frontend/dist /app/static

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AZURE_OPENAI_VOICE_CHOICE=alloy

# Gunicorn command with proper async worker
CMD ["gunicorn", "app:create_app", \
     "--worker-class", "aiohttp.GunicornWebWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "600"] 
