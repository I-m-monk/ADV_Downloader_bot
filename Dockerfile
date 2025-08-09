FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "8", "--timeout", "120"]
