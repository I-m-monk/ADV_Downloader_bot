FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV BOT_TOKEN=8063685071:AAFER9Rg-IIqqqcF-ejLV5H2OJHfN_Lj0WI
ENV WEBHOOK_URL=https://adv-downloader-bot.onrender.com/webhook

CMD ["gunicorn", "-b", "0.0.0.0:10000", "main:app"]
