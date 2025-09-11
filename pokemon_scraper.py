# pokemon_scraper.py
import os
import json
import time
import logging
import traceback
from typing import List, Tuple, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from flask import Flask, jsonify

# ---------------- Config ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ALGOLIA_URL = "https://vtvkm5urpx-2.algolianet.com/1/indexes/shopify_products_families/browse"
ALGOLIA_HEADERS = {
    "x-algolia-agent": "Algolia for JavaScript (5.23.4); Search (5.23.4); Browser",
    "x-algolia-api-key": "1d989f0839a992bbece9099e1b091f07",
    "x-algolia-application-id": "VTVKM5URPX",
}
ALGOLIA_PAYLOAD = {"hitsPerPage": 1000}

CACHE_FILE = "cache.json"
COLLECTION_URL = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"

# Force HTML fallback (Browserless backup)
FORCE_HTML = os.getenv("FORCE_HTML", "1") == "1"
BROWSERLESS_URL = os.getenv("BROWSERLESS_URL")  # e.g. "https://chrome.browserless.io/content?token=YOUR_TOKEN"

SAVE_HTML_SNAPSHOT = os.getenv("SAVE_HTML_SNAPSHOT", "1") == "1"

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ---------------- HTTP session with retries ----------------
def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","POST"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s

# ---------------- Telegram ----------------
def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_TOKEN/CHAT_ID not set, skipping Telegram")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode":"Markdown", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Telegram message sent, length=%d", len(message))
    except Exception as e:
        logger.error("Telegram send error: %s", e)

# ---------------- Cache ----------------
def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            return set(json.load(open(CACHE_FILE)))
        except:
            logger.warning("Failed to load cache")
    return set()

def save_cache(s: set):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(list(s), f)
    except:
        logger.warning("Failed to save cache")

# ---------------- Algolia ----------------
def get_from_algolia() -> List[str]:
    logger.info("Fetching from Algolia API...")
    try:
        session = build_session()
        r = session.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=ALGOLIA_PAYLOAD, timeout=20)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        links = [f"https://www.jbhifi.com.au/products/{h.get('handle')}" for h in hits if h.get("preamble")=="Card Game" and h.get("vendor")=="POKEMON TCG"]
        logger.info("Algolia links found: %d", len(links))
        return links
    except Exception as e:
        logger.error("Algolia fetch error: %s", e)
        return []

# ---------------- Browserless.io fallback ----------------
def get_from_browserless() -> List[str]:
    if not BROWSERLESS_URL:
        logger.warning("BROWSERLESS_URL not set, skipping JS render fallback")
        return []
    logger.info("Fetching via Browserless.io...")
    try:
        payload = {"url": COLLECTION_URL}
        r = requests.post(BROWSERLESS_URL, json=payload, timeout=30)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.select("a[href*='/products/']"):
            href = a.get("href")
            if href.startswith("/"):
                href = "https://www.jbhifi.com.au" + href
            if href not in links:
                links.append(href)
        logger.info("Browserless backup links found: %d", len(links))
        return links
    except Exception as e:
        logger.error("Browserless fetch error: %s", e)
        return []

# ---------------- Crawl ----------------
def crawl_links() -> List[str]:
    if not FORCE_HTML:
        links = get_from_algolia()
        if links:
            return links
        else:
            logger.warning("Algolia failed, using Browserless backup")
    # JS render fallback
    return get_from_browserless()

# ---------------- Flask app ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper running."

@app.route("/run")
def run():
    logger.info("---- /run triggered ----")
    out = {"success": False}
    try:
        links = crawl_links()
        cached = load_cache()
        new_links = [l for l in links if l not in cached]

        logger.info("Total links: %d, New links: %d", len(links), len(new_links))

        if new_links:
            batch_size = 25
            for i in range(0, len(new_links), batch_size):
                batch = new_links[i:i+batch_size]
                send_telegram_message("*New JB Hi-Fi Pokémon Products:*\n" + "\n".join(batch))
            cached.update(new_links)
            save_cache(cached)
        out.update({"success": True, "total_links": len(links), "new_links": len(new_links)})
    except Exception as e:
        logger.error("Error in /run: %s", e)
        out.update({"error": str(e)})
    return jsonify(out)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
