# ============================================================
# EcoFlow AI — Cloud Run container
# MyAI Future Hackathon · Track 4: Green Horizon
# ============================================================
FROM python:3.11-slim

# System deps for firebase-admin / grpc wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Cloud Run injects PORT at runtime (usually 8080)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# 1 worker is fine for Cloud Run — it auto-scales containers horizontally.
# Use a single uvicorn process; Cloud Run handles concurrency via instances.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
