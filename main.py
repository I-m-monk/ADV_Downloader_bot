from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler
import asyncio
import os

# Bot Token & Webhook URL
TOKEN = os.getenv("BOT_TOKEN", "8063685071:AAFER9Rg-IIqqqcF-ejLV5H2OJHfN_Lj0WI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://adv-downloader-bot.onrender.com/webhook")

app = Flask(__name__)

# Create Telegram Application
application = Application.builder().token(TOKEN).build()

# Commands
async def start(update: Update, context):
    await update.message.reply_text("Hello! ✅ Bot is running.")

application.add_handler(CommandHandler("start", start))

# Initialize and start bot before requests
async def init_bot():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set to: {WEBHOOK_URL}")

# Run bot initialization before first request
asyncio.get_event_loop().run_until_complete(init_bot())

@app.route("/")
def home():
    return "Bot is live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.create_task(application.process_update(update))
    except Exception as e:
        print("❌ Error in webhook:", e)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
