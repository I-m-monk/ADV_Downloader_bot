# force redeploy: 2025-08-09
# -*- coding: utf-8 -*-
"""
Telegram Video Extractor Bot (Webhook for Render)
- Async init fixed (awaited properly)
- Extra debug logs for /start and message handlers
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

# --- Config ---
TOKEN = os.environ.get('TG_BOT_TOKEN')
if not TOKEN:
    raise RuntimeError("TG_BOT_TOKEN environment variable not set.")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

application = Application.builder().token(TOKEN).build()
bot = Bot(token=TOKEN)

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
