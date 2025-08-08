# Use official Python image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Expose port used by Render
ENV PORT 8080
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 "main:app"
