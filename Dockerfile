# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# system deps for building/parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000

# Gunicorn + Flask wsgi app (main:app)
CMD ["gunicorn", "-b", "0.0.0.0:10000", "main:app", "--workers", "1", "--threads", "2", "--timeout", "120"]
