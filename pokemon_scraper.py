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
BROWSERLESS_URL = os.getenv("BROWSERLESS_URL")  # optional JS render backup

ALGOLIA_URL = "https://vtvkm5urpx-2.algolianet.com/1/indexes/shopify_products_families/browse"
ALGOLIA_HEADERS = {
    "x-algolia-agent": "Algolia for JavaScript (5.23.4); Search (5.23.4); Browser",
    "x-algolia-api-key": "1d989f0839a992bbece9099e1b091f07",
    "x-algolia-application-id": "VTVKM5URPX",
}
ALGOLIA_PAYLOAD = {"hitsPerPage": 1000}

CACHE_FILE = "cache.json"
COLLECTION_URL = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"

FORCE_HTML = os.getenv("FORCE_HTML", "1") == "1"
SAVE_HTML_SNAPSHOT = os.getenv("SAVE_HTML_SNAPSHOT", "1") == "1"

# ---------------- Logging ----------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ---------------- HTTP session with retries ----------------
def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","POST"])
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s

# ---------------- Telegram ----------------
def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram send")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode":"Markdown", "disable_web_page_preview": True}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message sent (length=%d)", len(message))
    except Exception as e:
        logger.error("Telegram send error: %s", e)

# ---------------- Cache ----------------
def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded cache (%d entries)", len(data))
            return set(data)
        except Exception as e:
            logger.error("Cache load error: %s", e)
    return set()

def save_cache(s: set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
        logger.info("Saved cache (%d entries)", len(s))
    except Exception as e:
        logger.error("Cache save error: %s", e)

# ---------------- Algolia ----------------
def get_from_algolia() -> List[str]:
    logger.info("Fetching from Algolia...")
    session = build_session()
    try:
        r = session.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=ALGOLIA_PAYLOAD, timeout=20)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        links = [f"https://www.jbhifi.com.au/products/{h['handle']}"
                 for h in hits if h.get("preamble")=="Card Game" and h.get("vendor")=="POKEMON TCG" and h.get("handle")]
        logger.info("Algolia filtered links: %d", len(links))
        return links
    except Exception as e:
        logger.error("Algolia fetch error: %s", e)
        return []

# ---------------- HTML fallback ----------------
def save_debug_html(content: str) -> str:
    ts = int(time.time())
    fn = f"debug_page_{ts}.html"
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved HTML snapshot: %s", fn)
        return fn
    except Exception as e:
        logger.error("Failed to save HTML snapshot: %s", e)
        return ""

def parse_html_for_links(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    found_links = []
    for a in soup.select("a[href*='/products/']"):
        href = a.get("href")
        if href.startswith("/"):
            href = "https://www.jbhifi.com.au" + href
        if href not in found_links:
            found_links.append(href)
    return found_links

def get_from_html() -> Tuple[List[str], Optional[str]]:
    logger.info("HTML fallback fetching %s", COLLECTION_URL)
    session = build_session()
    try:
        r = session.get(COLLECTION_URL, timeout=25)
        r.raise_for_status()
        links = parse_html_for_links(r.text)
        debug_path = save_debug_html(r.text) if SAVE_HTML_SNAPSHOT and not links else None
        logger.info("HTML fallback found %d links", len(links))
        return links, debug_path
    except Exception as e:
        logger.error("HTML fetch error: %s", e)
        return [], None

# ---------------- Main crawler ----------------
def crawl_links() -> dict:
    result = {"source": None, "links": [], "debug_html": None}
    links = []

    if not FORCE_HTML:
        links = get_from_algolia()
        if links:
            result["source"] = "algolia"
    if not links:
        links, debug_path = get_from_html()
        result["source"] = "html"
        result["debug_html"] = debug_path
    result["links"] = links
    return result

# ---------------- Flask app ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper running"

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
    crawl_result = crawl_links()
    links = crawl_result.get("links", [])
    debug_path = crawl_result.get("debug_html")
    cached = load_cache()
    new_links = [l for l in links if l not in cached]
    logger.info("Total links: %d, New links: %d", len(links), len(new_links))

    if new_links:
        batch_size = 25
        for i in range(0, len(new_links), batch_size):
            batch = new_links[i:i+batch_size]
            send_telegram_message("*New JB Hi-Fi Pokémon Products:*\n\n" + "\n".join(batch))
        cached.update(new_links)
        save_cache(cached)
    else:
        logger.info("No new links to send via Telegram")

    return jsonify({
        "total_links": len(links),
        "new_links": len(new_links),
        "debug_html": debug_path
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting app on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
