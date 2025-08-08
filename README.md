# Telegram Video Extractor Bot (Ready-to-Deploy)

**What this package contains**
- `main.py` : Flask webhook endpoint + python-telegram-bot handlers + robust video extraction (pornxp.me, ahcdn.com)
- `requirements.txt` : dependencies (includes `python-telegram-bot[webhooks]`)
- `Dockerfile` : ready for Render deployment (Gunicorn + Flask)
- `render.yaml` : sample Render service spec
- No `runtime.txt` (Docker used instead)

## Setup (Render)
1. Create a new Web Service on Render, connect your GitHub repo (or upload zip).
2. In Render dashboard, set environment variable `TG_BOT_TOKEN` with your bot token.
3. Deploy the service. Render will build the Docker image and run the container.
4. Set your Telegram webhook (replace <your-deploy-url>):
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-service>.onrender.com/webhook
   ```
   You can run this in your terminal (curl) or via browser.
5. Hit `/start` in your bot and send a video page URL.

## Local testing
- For local testing you can run:
  ```bash
  export TG_BOT_TOKEN="your_token"
  python main.py
  ```
  Then use `ngrok http 8080` and set webhook to `https://<ngrok-id>.ngrok.io/webhook`

## Notes & Limitations
- The bot attempts to download videos and send them directly. If the file is large (>50MB) it will not stream through the bot and will instead return the direct URL.
- Some hosts may block Render IPs. If downloads fail with network errors, consider using a proxy or deploying on a VM/VPS with different IP.
- The extraction logic is robust but may need site-specific tweaks for tricky obfuscated players.

## Troubleshooting
- If you see `Conflict: terminated by other getUpdates request`, ensure you're using webhook only (no polling).
- Check Render logs for stack traces. Logging is enabled in `main.py`.
