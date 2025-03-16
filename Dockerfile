# Frontend build
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/ .
RUN npm install && npm run build

# Python backend
FROM python:3.10-slim  # Must match Azure's Python version
WORKDIR /app

# Install Python deps first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .
COPY --from=frontend-builder /frontend/dist /app/static

# Gunicorn command
CMD ["gunicorn", "app:create_app", "--worker-class", "aiohttp.worker.GunicornUVLoopWebWorker", "--bind", "0.0.0.0:8000"]
