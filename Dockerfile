# Python base image
FROM python:3.11-slim

# Working directory
WORKDIR /app

# Copy files
COPY requirements.txt requirements.txt
COPY main.py main.py

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Environment variables
ENV PORT=10000

# Start app with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "main:app"]
