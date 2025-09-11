import os
import json
import logging
import requests
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

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
)

# ---------------- Telegram ----------------
def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram not configured, skipping message send")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logging.info("Sent Telegram message")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

# ---------------- Cache ----------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Cache load error: {e}")
    return set()

def save_cache(links_set):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(list(links_set), f)
        logging.info("Cache saved")
    except Exception as e:
        logging.error(f"Cache save error: {e}")

# ---------------- Algolia Scraper ----------------
def get_from_algolia():
    logging.info("Fetching from Algolia API...")
    try:
        r = requests.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=ALGOLIA_PAYLOAD, timeout=20)
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        logging.info(f"Algolia returned {len(hits)} hits")

        links = []
        for hit in hits:
            if hit.get("preamble") == "Card Game" and hit.get("vendor") == "POKEMON TCG":
                handle = hit.get("handle")
                if handle:
                    links.append(f"https://www.jbhifi.com.au/products/{handle}")

        logging.info(f"Filtered Pokémon links: {len(links)}")
        return links
    except Exception as e:
        logging.error(f"Algolia fetch error: {e}")
        return []

# ---------------- HTML Fallback ----------------
def get_from_html():
    logging.info("Fallback: fetching from HTML page...")
    try:
        r = requests.get(COLLECTION_URL, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.select("a[href*='/products/']"):
            href = a.get("href")
            if href and "/products/" in href:
                if href.startswith("/"):
                    href = "https://www.jbhifi.com.au" + href
                links.append(href)
        logging.info(f"HTML parsed links: {len(links)}")
        return links
    except Exception as e:
        logging.error(f"HTML fetch error: {e}")
        return []

# ---------------- Main Crawl ----------------
def crawl_links():
    links = get_from_html()
    # links = get_from_algolia()
    # if not links:
    #     links = get_from_html()
    return links

# ---------------- Flask App ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper running!"

@app.route("/run")
def run():
    logging.info("----- /run triggered -----")
    scraped_links = crawl_links()
    cached_links = load_cache()
    new_links = [l for l in scraped_links if l not in cached_links]

    logging.info(f"New links: {len(new_links)}")

    if new_links:
        batch_size = 20
        for i in range(0, len(new_links), batch_size):
            batch = new_links[i:i+batch_size]
            message = "*New JB Hi-Fi Pokémon Products:*\n\n" + "\n".join(batch)
            send_telegram_message(message)

        cached_links.update(new_links)
        save_cache(cached_links)
    else:
        logging.info("No new links")

    return jsonify({
        "total_scraped": len(scraped_links),
        "new_links_sent": len(new_links),
        "links": scraped_links
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
