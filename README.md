# Adv Downloader Bot (Render-ready)

## Setup
1. Create a Render Web Service (Docker).
2. In **Environment Variables**, add:
   - `TG_BOT_TOKEN` → Your Telegram bot token from BotFather.
3. Deploy the repo with the provided `Dockerfile`.

## Set Webhook (from your PC)
Run this command, replacing `YOUR_TOKEN` and `YOUR_URL` with your actual bot token and Render service URL:

```bash
curl -X POST "https://api.telegram.org/botYOUR_TOKEN/setWebhook" --data-urlencode "url=YOUR_URL/webhook"
