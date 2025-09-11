import os
import json
import logging
import traceback
import time
from typing import List, Tuple
import requests
from flask import Flask, jsonify
from bs4 import BeautifulSoup

# ---------------- Config ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN")

ALGOLIA_URL = "https://vtvkm5urpx-2.algolianet.com/1/indexes/shopify_products_families/browse"
ALGOLIA_HEADERS = {
    "x-algolia-agent": "Algolia for JavaScript (5.23.4); Search (5.23.4); Browser",
    "x-algolia-api-key": "1d989f0839a992bbece9099e1b091f07",
    "x-algolia-application-id": "VTVKM5URPX",
}
ALGOLIA_PAYLOAD = {"hitsPerPage": 1000}
COLLECTION_URL = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"
CACHE_FILE = "cache.json"

# ---------------- Logging ----------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# ---------------- Cache ----------------
def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            return set(json.load(open(CACHE_FILE)))
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
    return set()

def save_cache(s: set):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(list(s), f)
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")

# ---------------- Telegram ----------------
def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping send")
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                          json={"chat_id": TELEGRAM_CHAT_ID,
                                "text": message,
                                "parse_mode":"Markdown",
                                "disable_web_page_preview":True},
                          timeout=10)
        r.raise_for_status()
        logger.info(f"Telegram sent message length={len(message)}")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

# ---------------- Algolia fetch ----------------
def get_from_algolia() -> List[str]:
    logger.info("Fetching from Algolia API...")
    try:
        r = requests.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=ALGOLIA_PAYLOAD, timeout=20)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        links = [f"https://www.jbhifi.com.au/products/{h['handle']}" 
                 for h in hits 
                 if h.get("preamble") == "Card Game" and h.get("vendor") == "POKEMON TCG" and h.get("tags") == "InStock" and h.get("handle")]
        logger.info(f"Algolia returned {len(links)} Pokémon links")
        return links
    except Exception as e:
        logger.error(f"Algolia fetch error: {e}")
        return []

# ---------------- Browserless fetch ----------------
def save_debug_html(content: str) -> str:
    ts = int(time.time())
    fn = f"debug_browserless_{ts}.html"
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Saved debug HTML to {fn}")
        return fn
    except Exception as e:
        logger.error(f"Failed to save debug HTML: {e}")
        return ""

def get_from_browserless() -> List[str]:
    if not BROWSERLESS_TOKEN:
        logger.warning("BROWSERLESS_TOKEN not set, skipping Browserless")
        return []
    logger.info("Fetching via Browserless...")
    try:
        api_url = f"https://chrome.browserless.io/content?token={BROWSERLESS_TOKEN}&url={COLLECTION_URL}&options={{\"waitUntil\":\"networkidle0\"}}"
        r = requests.get(api_url, timeout=30)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        links = []
        samples = []
        for a in soup.select("a[href*='/products/']"):
            href = a.get("href")
            if href.startswith("/"):
                href = "https://www.jbhifi.com.au" + href
            if href not in links:
                links.append(href)
                if len(samples)<20:
                    samples.append((href, a.get_text(strip=True)))
        if not links:
            debug_file = save_debug_html(html)
            logger.warning(f"No links found via Browserless. Debug saved: {debug_file}")
        else:
            logger.info(f"Browserless fetched {len(links)} links. Sample: {samples[:5]}")
        return links
    except Exception as e:
        logger.error(f"Browserless fetch error: {e}")
        logger.debug(traceback.format_exc())
        return []

# ---------------- Crawl ----------------
def crawl_links() -> List[str]:
    links = get_from_browserless()
    # links = get_from_algolia()
    # if not links:
    #     logger.info("Algolia empty, fallback to Browserless")
    #     links = get_from_browserless()
    return links

# ---------------- Flask ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper (Algolia + Browserless) running."

@app.route("/debug/<path:filename>")
def debug_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html"}
    except Exception as e:
        return f"Error: {e}", 404

@app.route("/run")
def run():
    logger.info("---- /run triggered ----")
    links = crawl_links()
    cached = load_cache()
    new_links = [l for l in links if l not in cached]
    if new_links:
        send_telegram_message("*New JB Hi-Fi Pokémon Products:*\n" + "\n".join(new_links))
        cached.update(new_links)
        save_cache(cached)
    return jsonify({
        "total_links": len(links),
        "new_links": len(new_links)
    })

if __name__ == "__main__":
    logger.info("Starting app on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
