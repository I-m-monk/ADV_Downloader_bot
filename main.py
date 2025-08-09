# main.py
# Simple webhook-based Telegram video downloader (synchronous Flask + background thread)
import os
import re
import logging
import threading
from io import BytesIO
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, Response, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adv-downloader")

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
if not TG_BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN environment variable not set!")

TELEGRAM_API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB Telegram limit for uploads (bot API)

app = Flask(__name__)

URL_RE = re.compile(r'(https?://[^\s]+)')

def send_message(chat_id, text):
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", data={"chat_id": chat_id, "text": text})
        logger.info("sendMessage: %s %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("Failed to send message: %s", e)

def send_document(chat_id, fileobj, filename):
    try:
        files = {"document": (filename, fileobj)}
        data = {"chat_id": chat_id}
        r = requests.post(f"{TELEGRAM_API}/sendDocument", data=data, files=files, timeout=120)
        logger.info("sendDocument: %s %s", r.status_code, r.text)
        return r.ok
    except Exception:
        logger.exception("send_document failed")
        return False

def send_video(chat_id, fileobj, filename):
    try:
        files = {"video": (filename, fileobj)}
        data = {"chat_id": chat_id}
        r = requests.post(f"{TELEGRAM_API}/sendVideo", data=data, files=files, timeout=120)
        logger.info("sendVideo: %s %s", r.status_code, r.text)
        return r.ok
    except Exception:
        logger.exception("send_video failed")
        return False

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

    # <video> tag
    video = soup.find('video')
    if video:
        src = video.get('src')
        if src:
            return urljoin(url, src)
        source = video.find('source')
        if source and source.get('src'):
            return urljoin(url, source.get('src'))

    # og:video
    og = soup.find('meta', property='og:video')
    if og and og.get('content'):
        return urljoin(url, og.get('content'))

    # JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            import json
            data = json.loads(script.string or '{}')
            if isinstance(data, dict):
                for key in ('contentUrl', 'url', 'embedUrl'):
                    if data.get(key):
                        return urljoin(url, data.get(key))
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        for key in ('contentUrl', 'url', 'embedUrl'):
                            if entry.get(key):
                                return urljoin(url, entry.get(key))
        except Exception:
            pass

    # direct mp4 urls inside html
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

    # if final is direct video
    if re.search(r'\.(mp4|m3u8|webm|ogg)(?:$|\?)', final, re.IGNORECASE):
        return final

    try:
        r = session.get(final, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        logger.warning('Failed to fetch page: %s', e)
        return None

    # site-specific small heuristics (ahcdn / pornxp)
    if 'pornxp.me' in final:
        found = extract_video_from_html(session, final, html)
        if found:
            return found
        m = re.search(r'["\']file["\']\s*:\s*["\'](https?://[^"\']+)["\']', html)
        if m:
            return m.group(1)

    if 'ahcdn' in final or 'ahcdn.com' in final:
        found = extract_video_from_html(session, final, html)
        if found:
            return found
        m = re.search(r'data-src=["\'](https?://[^"\']+)["\']', html)
        if m:
            return m.group(1)

    return extract_video_from_html(session, final, html)

def process_link(chat_id, url):
    session = requests.Session()
    send_message(chat_id, f"Processing: {url}")
    vid_url = extract_video_url(session, url)
    if not vid_url:
        send_message(chat_id, "Sorry, couldn't extract a direct video URL from that page.")
        return

    # Try HEAD to get size
    try:
        h = session.head(vid_url, allow_redirects=True, timeout=10)
        size = int(h.headers.get('Content-Length', 0))
        ctype = h.headers.get('Content-Type', 'application/octet-stream')
    except Exception:
        size = 0
        ctype = 'application/octet-stream'

    logger.info("Detected content-type=%s size=%s", ctype, size)

    if size and size > MAX_UPLOAD_BYTES:
        send_message(chat_id, f"Video is large ({size/(1024*1024):.1f} MB). Sending direct URL:\n{vid_url}")
        return

    # Stream download but stop if exceed MAX_UPLOAD_BYTES
    try:
        resp = session.get(vid_url, stream=True, timeout=60)
        resp.raise_for_status()
        bio = BytesIO()
        for chunk in resp.iter_content(chunk_size=256*1024):
            if not chunk:
                break
            bio.write(chunk)
            if bio.tell() > MAX_UPLOAD_BYTES:
                logger.info("Stream exceeded max upload size; aborting upload")
                send_message(chat_id, f"Video is larger than {MAX_UPLOAD_BYTES/(1024*1024):.0f}MB — direct URL:\n{vid_url}")
                return
        bio.seek(0)
        # prefer sendVideo if content-type is video and small
        if ctype.startswith('video'):
            ok = send_video(chat_id, bio, "video.mp4")
            if not ok:
                # fallback to document
                bio.seek(0)
                send_document(chat_id, bio, "video.mp4")
        else:
            bio.seek(0)
            send_document(chat_id, bio, "file.bin")
    except Exception as e:
        logger.exception("Failed to download/send video: %s", e)
        send_message(chat_id, "Error while downloading or sending the video. Direct URL:\n" + vid_url)

def process_message(msg):
    # msg is the Telegram 'message' dict
    chat_id = None
    if 'chat' in msg:
        chat_id = msg['chat']['id']
    else:
        logger.warning("No chat id found in message")
        return

    text = msg.get('text') or msg.get('caption') or ''
    if not text:
        send_message(chat_id, "Koi text ya URL bhejo.")
        return

    # /start
    if text.strip().startswith('/start'):
        send_message(chat_id, "Hi — send me a video page URL (pornxp.me or ahcdn.com). I'll try to extract and send the video.")
        return

    urls = find_urls(text)
    if not urls:
        send_message(chat_id, "Koi URL bhejo pehle — I need a link to extract the video from.")
        return

    # process sequentially (could be parallel if wanted)
    for url in urls:
        try:
            process_link(chat_id, url)
        except Exception:
            logger.exception("Processing link failed for %s", url)
            send_message(chat_id, f"Failed processing: {url}")

@app.route('/webhook', methods=['POST'])
def webhook():
    # Return quickly, process in background to avoid Telegram timeouts
    try:
        update = request.get_json(force=True)
    except Exception:
        return Response("bad request", status=400)

    # spawn a thread to handle updates
    def worker(u):
        try:
            logger.info("Background worker handling update")
            if 'message' in u:
                process_message(u['message'])
            elif 'edited_message' in u:
                process_message(u['edited_message'])
            else:
                logger.info("Unhandled update type")
        except Exception:
            logger.exception("Error in worker")

    threading.Thread(target=worker, args=(update,), daemon=True).start()
    return Response("OK", status=200)

@app.route('/')
def index():
    return "OK - Adv Downloader Bot"

@app.route('/healthz')
def healthz():
    return jsonify(status="ok")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
