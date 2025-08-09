# -*- coding: utf-8 -*-
"""
Telegram Video Extractor Bot (Webhook for Render)
Fixes:
- Awaited application.initialize() properly
- Added extra logging for /webhook hits
- Better error handling
"""

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

# --- Configuration ---
TOKEN = os.environ.get('TG_BOT_TOKEN')  # Set in Render Env Vars
if not TOKEN:
    raise RuntimeError('TG_BOT_TOKEN environment variable not set.')

# Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram application
application = Application.builder().token(TOKEN).build()
bot = Bot(token=TOKEN)

# --- URL extraction helpers ---
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
    if video:
        src = video.get('src')
        if src:
            return requests.compat.urljoin(url, src)
        source = video.find('source')
        if source and source.get('src'):
            return requests.compat.urljoin(url, source.get('src'))

    og = soup.find('meta', property='og:video')
    if og and og.get('content'):
        return requests.compat.urljoin(url, og.get('content'))

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            import json
            data = json.loads(script.string or '{}')
            if isinstance(data, dict):
                for key in ('contentUrl', 'url', 'embedUrl'):
                    if data.get(key):
                        return requests.compat.urljoin(url, data.get(key))
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        for key in ('contentUrl', 'url', 'embedUrl'):
                            if entry.get(key):
                                return requests.compat.urljoin(url, entry.get(key))
        except Exception:
            pass

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
    logger.info('Final resolved url: %s', final)

    if re.search(r'\.(mp4|m3u8|webm|ogg)(?:$|\?)', final, re.IGNORECASE):
        return final

    try:
        r = session.get(final, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        logger.warning('Failed to fetch page: %s', e)
        return None

    if 'pornxp.me' in final:
        found = extract_video_from_html(session, final, html)
        if found:
            return found
        m = re.search(r'["\']file["\']\s*:\s*["\'](https?://[^"\']+)["\']', html)
        if m:
            return m.group(1)

    if 'ahcdn.com' in final or 'ahcdn' in final:
        found = extract_video_from_html(session, final, html)
        if found:
            return found
        m = re.search(r'data-src=["\'](https?://[^"\']+)["\']', html)
        if m:
            return m.group(1)

    return extract_video_from_html(session, final, html)

# --- Telegram handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi — send me a video page URL (pornxp.me or ahcdn.com). I'll try to extract and send the video.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ''
    urls = find_urls(text)
    if not urls:
        await update.message.reply_text("Koi URL bhejo pehle — I need a link to extract the video from.")
        return
    session = requests.Session()
    for url in urls:
        await update.message.reply_text(f"Processing: {url}")
        vid_url = extract_video_url(session, url)
        if not vid_url:
            await update.message.reply_text("Sorry, couldn't extract a direct video URL from that page.")
            continue

        try:
            h = session.head(vid_url, allow_redirects=True, timeout=10)
            size = int(h.headers.get('Content-Length', 0))
            ctype = h.headers.get('Content-Type', 'application/octet-stream')
        except Exception:
            size = 0
            ctype = 'application/octet-stream'

        MAX_BYTES = 50 * 1024 * 1024
        if size and size > MAX_BYTES:
            await update.message.reply_text(
                f"Video seems large ({size/(1024*1024):.1f} MB). I will send the direct URL instead:\n{vid_url}"
            )
            continue

        try:
            resp = session.get(vid_url, stream=True, timeout=30)
            resp.raise_for_status()
            bio = BytesIO()
            for chunk in resp.iter_content(chunk_size=256*1024):
                if not chunk:
                    break
                bio.write(chunk)
                if bio.tell() > 100 * 1024 * 1024:
                    break
            bio.seek(0)
            if ctype.startswith('video'):
                await context.bot.send_video(chat_id=update.effective_chat.id, video=bio, filename='video.mp4')
            else:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=bio, filename='file.bin')
        except Exception as e:
            logger.exception('Failed to download/send video: %s', e)
            await update.message.reply_text("Error while downloading or sending the video. Sending direct URL instead:\n" + vid_url)

# Register handlers
application.add_handler(CommandHandler('start', start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Properly initialize Application
asyncio.run(application.initialize())

# --- Webhook endpoint ---
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    logger.info("Webhook hit received from Telegram")
    try:
        update_json = request.get_json(force=True)
        update = Update.de_json(update_json, application.bot)
        application.update_queue.put_nowait(update)
        return Response('OK', status=200)
    except Exception as e:
        logger.exception("Failed to handle update: %s", e)
        return Response('Error', status=500)

@app.route('/healthz', methods=['GET'])
def healthz():
    return Response('ok', status=200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
