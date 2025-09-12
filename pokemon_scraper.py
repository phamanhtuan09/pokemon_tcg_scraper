import os
import json
import time
import logging
from typing import List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, jsonify, send_file
from bs4 import BeautifulSoup
import asyncio
from pyppeteer import launch

# ---------------- Config ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CACHE_FILE = "cache.json"
COLLECTION_URL = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"
SAVE_HTML_SNAPSHOT = os.getenv("SAVE_HTML_SNAPSHOT", "1") == "1"

ALGOLIA_URL = "https://vtvkm5urpx-2.algolianet.com/1/indexes/shopify_products_families/browse"
ALGOLIA_HEADERS = {
    "x-algolia-agent": "Algolia for JavaScript (5.23.4); Search (5.23.4); Browser",
    "x-algolia-api-key": "1d989f0839a992bbece9099e1b091f07",
    "x-algolia-application-id": "VTVKM5URPX",
}
ALGOLIA_PAYLOAD = {"hitsPerPage": 1000}

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ---------------- HTTP session ----------------
def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429,500,502,503,504])
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    })
    return s

# ---------------- Telegram ----------------
def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set, skip sending")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Sent Telegram message (len=%d)", len(message))
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
            logger.error("Failed to load cache: %s", e)
    return set()

def save_cache(s: set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
        logger.info("Saved cache (%d entries)", len(s))
    except Exception as e:
        logger.error("Failed to save cache: %s", e)

# ---------------- Algolia fetch ----------------
def get_from_algolia() -> List[str]:
    logger.info("Fetching from Algolia...")
    session = build_session()
    try:
        r = session.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=ALGOLIA_PAYLOAD, timeout=20)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        logger.info("Algolia returned %d hits", len(hits))
        links = []
        for hit in hits:
            if hit.get("preamble") == "Card Game" and hit.get("vendor") == "POKEMON TCG" and hit.get("tags") == "INSTOCK":
                handle = hit.get("handle")
                if handle:
                    links.append(f"https://www.jbhifi.com.au/products/{handle}")
        logger.info("Filtered Pokémon links (Algolia): %d", len(links))
        return links
    except Exception as e:
        logger.error("Algolia fetch error: %s", e)
        return []

# ---------------- Pyppeteer fallback ----------------
async def fetch_js_rendered_links(url: str) -> List[str]:
    logger.info("Pyppeteer fallback: rendering JS page %s", url)
    try:
        browser = await launch(
            headless=True,
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer"
            ],
            executablePath=os.getenv("PYPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium")
        )
        page = await browser.newPage()
        await page.setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        await page.goto(url, waitUntil='networkidle0', timeout=30000)
        content = await page.content()
        await browser.close()

        # Save debug HTML
        fn = None
        if SAVE_HTML_SNAPSHOT:
            fn = f"debug_page_{int(time.time())}.html"
            with open(fn, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Saved debug HTML: %s", fn)

        # Parse links
        soup = BeautifulSoup(content, "html.parser")
        links = []
        for a in soup.select("a[href*='/products/']"):
            href = a.get("href")
            if href and href.startswith("/"):
                href = "https://www.jbhifi.com.au" + href
            if href not in links:
                links.append(href)
        logger.info("Pyppeteer found %d product links", len(links))
        return links
    except Exception as e:
        logger.error("Browser fetch error: %s", e)
        return []

def get_from_pyppeteer(url: str) -> List[str]:
    return asyncio.run(fetch_js_rendered_links(url))

# ---------------- Main crawl ----------------
def crawl_links() -> List[str]:
    # links = get_from_algolia()
    # if links:
    #     return links
    # logger.warning("Algolia empty, fallback to Pyppeteer")
    return get_from_pyppeteer(COLLECTION_URL)

# ---------------- Flask ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper running."

@app.route("/run")
def run():
    logger.info("----- /run triggered -----")
    links = crawl_links()
    cached = load_cache()
    new_links = [l for l in links if l not in cached]
    logger.info("Total links: %d, new: %d", len(links), len(new_links))
    if new_links:
        batch_size = 25
        for i in range(0, len(new_links), batch_size):
            batch = new_links[i:i + batch_size]
            message = "*New JB Hi-Fi Pokémon Products:*\n\n" + "\n".join(batch)
            send_telegram_message(message)
        cached.update(new_links)
        save_cache(cached)
    return jsonify({
        "success": True,
        "total_links": len(links),
        "new_links": len(new_links)
    })

@app.route("/debug/<path:filename>")
def debug_file(filename):
    if os.path.exists(filename):
        return send_file(filename, mimetype="text/html")
    return f"Debug file {filename} not found", 404

if __name__ == "__main__":
    logger.info("Starting app on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
