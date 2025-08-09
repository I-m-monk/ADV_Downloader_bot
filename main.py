import os
import asyncio
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---- CONFIG ----
TOKEN = "8063685071:AAFER9Rg-IIqqqcF-ejLV5H2OJHfN_Lj0WI"
WEBHOOK_URL = "https://adv-downloader-bot.onrender.com/webhook"

# ---- TELEGRAM BOT ----
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Bot is working ✅")

application.add_handler(CommandHandler("start", start))

# ---- FLASK APP ----
app = Flask(__name__)
bot_started = False

async def init_bot():
    global bot_started
    if not bot_started:
        await application.initialize()
        await application.start()
        bot_started = True
        print("Bot started ✅")

def ensure_event_loop():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop = asyncio.get_event_loop()
    return loop

@app.before_request
def before_request():
    loop = ensure_event_loop()
    loop.create_task(init_bot())

@app.route("/", methods=["GET"])
def index():
    return "Bot server is running 🚀"

@app.route("/webhook", methods=["POST"])
def webhook():
    loop = ensure_event_loop()
    update = Update.de_json(request.get_json(force=True), application.bot)
    loop.create_task(application.process_update(update))
    return Response("OK", status=200)

# ---- START SERVER ----
if __name__ == "__main__":
    loop = ensure_event_loop()
    loop.run_until_complete(application.bot.set_webhook(WEBHOOK_URL))
    app.run(host="0.0.0.0", port=10000)
