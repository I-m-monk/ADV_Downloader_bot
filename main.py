import os
import re
import logging
import asyncio
from io import BytesIO
from flask import Flask, request, Response
import requests
from bs4 import BeautifulSoup
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Config ---
TOKEN = os.environ.get('TG_BOT_TOKEN')
if not TOKEN:
    raise RuntimeError("TG_BOT_TOKEN environment variable not set.")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

application = Application.builder().token(TOKEN).build()
bot = Bot(token=TOKEN)
bot_ready = False  # Bot init flag

# --- Helpers ---
URL_RE = re.compile(r'(https?://[^\s]+)')

def find_urls(text):
    return URL_RE.findall(text or "")

def get_final_url(session, url):
    try:
        r = session.head(url, allow_redirects=True, timeout=10)
        return r.url
    except Exception:
        return url

def extract_video_from_html(session, url, html_text):
    soup = BeautifulSoup(html_text, 'html.parser')

    video = soup.find('video')
    if video and video.get('src'):
        return requests.compat.urljoin(url, video.get('src'))
    if video:
        source = video.find('source')
        if source and source.get('src'):
            return requests.compat.urljoin(url, source.get('src'))

    og = soup.find('meta', property='og:video')
    if og and og.get('content'):
        return requests.compat.urljoin(url, og.get('content'))

    patterns = [
        r'https?://[^\s"\']+\.mp4(?:\?[^\s"\']*)?',
        r'https?://[^\s"\']+\.m3u8(?:\?[^\s"\']*)?',
    ]
    for pat in patterns:
        m = re.search(pat, html_text)
        if m:
            return m.group(0)

    return None

def extract_video_url(session, url):
    logger.info('Extracting video for %s', url)
    final = get_final_url(session, url)

    if re.search(r'\.(mp4|m3u8|webm|ogg)(?:$|\?)', final, re.IGNORECASE):
        return final

    try:
        r = session.get(final, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception:
        return None

    return extract_video_from_html(session, final, html)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi — send me a video page URL, I'll try to get the direct link.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = find_urls(update.message.text or '')
    if not urls:
        await update.message.reply_text("Please send a valid URL.")
        return

    session = requests.Session()
    for url in urls:
        await update.message.reply_text(f"Processing: {url}")
        vid_url = extract_video_url(session, url)
        if not vid_url:
            await update.message.reply_text("Could not extract a direct video URL.")
            continue
        await update.message.reply_text(f"Direct link:\n{vid_url}")

application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Init Bot ---
async def init_bot_once():
    global bot_ready
    if not bot_ready:
        await application.initialize()
        await application.start()
        bot_ready = True
        logger.info("Bot initialized and started.")

@app.before_request
def ensure_bot_started():
    if not bot_ready:
        asyncio.get_event_loop().create_task(init_bot_once())

# --- Webhook ---
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        update_json = request.get_json(force=True)
        update = Update.de_json(update_json, application.bot)
        asyncio.get_event_loop().create_task(application.process_update(update))
        return Response('OK', status=200)
    except Exception as e:
        logger.exception("Failed to handle update: %s", e)
        return Response('Error', status=500)

@app.route('/healthz')
def healthz():
    return Response('ok', status=200)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
