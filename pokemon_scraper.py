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

# Force HTML fallback even if Algolia works (useful for testing)
FORCE_HTML = os.getenv("FORCE_HTML", "1") == "1"

# Whether to save HTML snapshot when no product anchors found
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
    retries = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    # set common headers
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s

# ---------------- Telegram helper ----------------
def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set — skipping Telegram send")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message sent (length=%d)", len(message))
    except Exception as e:
        logger.error("Telegram send error: %s", e)

# ---------------- Cache helpers ----------------
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

# ---------------- Algolia fetch (with logging) ----------------
def get_from_algolia() -> List[str]:
    logger.info("Attempting to fetch from Algolia (URL: %s)", ALGOLIA_URL)
    session = build_session()
    try:
        logger.debug("Algolia request headers: %s", ALGOLIA_HEADERS)
        r = session.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=ALGOLIA_PAYLOAD, timeout=20)
        logger.info("Algolia response status: %s", r.status_code)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        logger.info("Algolia returned %d hits", len(hits))
        if len(hits) > 0:
            logger.debug("Sample hit keys: %s", list(hits[0].keys()))
            # log sample of first hit (truncated)
            logger.debug("Sample hit[0]: %s", {k: (str(hits[0].get(k))[:200] + '...') if isinstance(hits[0].get(k), str) and len(hits[0].get(k))>200 else hits[0].get(k) for k in list(hits[0].keys())[:10]})

        links = []
        for hit in hits:
            try:
                if hit.get("preamble") == "Card Game" and hit.get("vendor") == "POKEMON TCG":
                    handle = hit.get("handle")
                    if handle:
                        url = f"https://www.jbhifi.com.au/products/{handle}"
                        links.append(url)
            except Exception:
                logger.debug("Error processing hit: %s", traceback.format_exc())

        logger.info("Algolia filtered Pokémon links: %d", len(links))
        if len(links) > 5:
            logger.debug("Sample links (Algolia): %s", links[:5])
        return links
    except Exception as e:
        logger.error("Algolia fetch error: %s", e)
        return []

# ---------------- HTML fallback (detailed logging) ----------------
def save_debug_html(content: str) -> str:
    ts = int(time.time())
    fn = f"debug_page_{ts}.html"
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved HTML snapshot to %s", fn)
        return fn
    except Exception as e:
        logger.error("Failed to save HTML snapshot: %s", e)
        return ""

def parse_html_for_links(html: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    soup = BeautifulSoup(html, "html.parser")
    found_links = []
    samples = []  # list of tuples (href, text)
    # Try multiple selectors (in decreasing specificity)
    selectors = [
        "a.card-link",
        "a.product-item",
        "a[href*='/products/']",
        "div.product-item a",   # fallback variations
        "a[href^='/products/']"
    ]
    total_found = 0
    for sel in selectors:
        elems = soup.select(sel)
        logger.info("Selector '%s' -> found %d elements", sel, len(elems))
        for e in elems:
            href = e.get("href") or e.get("data-href") or e.get("data-url")
            text = (e.get_text() or "").strip()
            if href and "/products/" in href:
                if href.startswith("/"):
                    href = "https://www.jbhifi.com.au" + href
                if href not in found_links:
                    found_links.append(href)
                    if len(samples) < 20:
                        samples.append((href, text[:120]))
        total_found += len(elems)
    logger.info("Total unique product links parsed: %d (from selectors total elements %d)", len(found_links), total_found)
    return found_links, samples

def get_from_html() -> Tuple[List[str], Optional[str], List[Tuple[str,str]]]:
    """
    Returns (links, debug_html_path or None, samples)
    """
    logger.info("HTML fallback: fetching %s", COLLECTION_URL)
    session = build_session()
    try:
        r = session.get(COLLECTION_URL, timeout=25)
        logger.info("HTML response status: %s, content-length: %s", r.status_code, r.headers.get("Content-Length"))
        r.raise_for_status()
        content = r.text
        logger.debug("HTML snippet: %s", content[:800].replace("\n"," ") )
        links, samples = parse_html_for_links(content)
        debug_path = None
        if not links:
            logger.warning("No product links found by selectors. Saving debug HTML for inspection.")
            if SAVE_HTML_SNAPSHOT:
                debug_path = save_debug_html(content)
        else:
            logger.info("Found %d links via HTML fallback", len(links))
            if len(samples) > 0:
                logger.info("Sample parsed anchors (href, text):")
                for href, text in samples[:10]:
                    logger.info(" - %s | %s", href, text)
        return links, debug_path, samples
    except Exception as e:
        logger.error("HTML fetch/parsing error: %s", e)
        logger.debug(traceback.format_exc())
        return [], (save_debug_html(r.text) if 'r' in locals() and SAVE_HTML_SNAPSHOT else None), []

# ---------------- Main crawl ----------------
def crawl_links() -> dict:
    """
    Returns dict with structure:
    {
        "source": "algolia" or "html",
        "links": [...],
        "debug_html": "debug_page_....html" or None,
        "sample": [...],
    }
    """
    result = {"source": None, "links": [], "debug_html": None, "sample": []}

    if not FORCE_HTML:
        logger.info("Trying Algolia first (FORCE_HTML not set)")
        algolia_links = get_from_algolia()
        if algolia_links:
            result["source"] = "algolia"
            result["links"] = list(dict.fromkeys(algolia_links))  # dedupe preserve order
            return result
        else:
            logger.warning("Algolia returned no links or failed; will fallback to HTML")
    else:
        logger.info("FORCE_HTML is set -> skipping Algolia and using HTML fallback")

    # HTML fallback
    links, debug_path, samples = get_from_html()
    result["source"] = "html"
    result["links"] = list(dict.fromkeys(links))
    result["debug_html"] = debug_path
    result["sample"] = samples
    return result

# ---------------- Flask app & endpoints ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper (Algolia + HTML fallback) running."

@app.route("/run")
def run():
    logger.info("---- /run triggered ----")
    out = {"success": False}
    try:
        crawl_result = crawl_links()
        links = crawl_result["links"]
        debug_path = crawl_result.get("debug_html")
        src = crawl_result["source"]
        samples = crawl_result.get("sample", [])

        cached = load_cache()
        new_links = [l for l in links if l not in cached]

        logger.info("Total links found: %d, New links: %d, Source: %s", len(links), len(new_links), src)

        if new_links:
            batch_size = 25
            for i in range(0, len(new_links), batch_size):
                batch = new_links[i:i+batch_size]
                message = "*New JB Hi-Fi Pokémon Products:*\n\n" + "\n".join(batch)
                send_telegram_message(message)
            cached.update(new_links)
            save_cache(cached)
        else:
            logger.info("No new links to send via Telegram")

        out.update({
            "success": True,
            "source": src,
            "total_links": len(links),
            "new_links": len(new_links),
            "debug_html": debug_path,
            "samples": samples[:10]
        })
    except Exception as e:
        logger.error("Unhandled error in /run: %s", e)
        logger.debug(traceback.format_exc())
        out.update({"error": str(e)})
    return jsonify(out)

if __name__ == "__main__":
    logger.info("Starting app on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
