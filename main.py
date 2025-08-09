import os
import asyncio
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = "8063685071:AAFER9Rg-IIqqqcF-ejLV5H2OJHfN_Lj0WI"
WEBHOOK_URL = "https://adv-downloader-bot.onrender.com/webhook"

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# /start command
async def start(update: Update, context):
    await update.message.reply_text("Hello! Bot is working fine ✅")

# Any text message
async def echo(update: Update, context):
    await update.message.reply_text(f"You said: {update.message.text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return Response("OK", status=200)

@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    # Set webhook at start
    asyncio.run(application.bot.set_webhook(WEBHOOK_URL))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
