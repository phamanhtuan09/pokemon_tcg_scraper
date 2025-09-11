import json
import os
import random
import time
import logging
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import requests

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

# ---------------- Telegram ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

import requests
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logging.info(f"Telegram message sent, length={len(message)} chars")
        return r.json()
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
        return None

# ---------------- Cache ----------------
CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            cached = set(json.load(open(CACHE_FILE)))
            logging.info(f"Loaded {len(cached)} cached links")
            return cached
        except Exception as e:
            logging.error(f"Cache load error: {e}")
    return set()

def save_cache(links_set):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(list(links_set), f)
        logging.info(f"Saved {len(links_set)} links to cache")
    except Exception as e:
        logging.error(f"Cache save error: {e}")

# ---------------- Scraper ----------------
URL = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"

def crawl_links():
    logging.info("Starting Playwright scraping...")
    links = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1024, "height": 768},
            java_script_enabled=True
        )
        page = context.new_page()

        # Debug network requests/responses
        page.on("request", lambda r: logging.debug(f"Request: {r.url}"))
        page.on("response", lambda r: logging.debug(f"Response: {r.url} -> {r.status}"))

        try:
            page.goto(URL, wait_until="networkidle", timeout=120000)
            logging.info(f"Page loaded successfully: {URL}")
        except PlaywrightTimeoutError as e:
            logging.error(f"Page.goto timeout: {e}")
            page.screenshot(path="error_screenshot.png")
            browser.close()
            return []

        # Scroll batch nhỏ để tiết kiệm memory
        last_height = 0
        max_scroll_batches = 10
        for batch in range(max_scroll_batches):
            for i in range(3):  # 3 lần mỗi batch
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(random.uniform(1.0, 2.5))  # random delay chống bot
            new_height = page.evaluate("document.body.scrollHeight")
            logging.info(f"Scroll batch {i+1}, new_height={new_height}")
            if new_height == last_height:
                logging.info("No more scroll, reached bottom")
                break
            last_height = new_height
    
            # Lấy link từng batch
            elems = page.query_selector_all("a[href*='/products/']")
            for e in elems:
                href = e.get_attribute("href")
                if href and "/products/" in href:
                    if href.startswith("/"):
                        href = "https://www.jbhifi.com.au" + href
                    links.add(href)
            logging.info(f"Links collected so far: {len(links)}")

        browser.close()
    logging.info(f"Total links scraped: {len(links)}")
    return list(links)

# ---------------- Flask App ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "JB Hi-Fi Pokémon scraper running!"

@app.route("/run")
def run():
    logging.info("----- /run endpoint triggered -----")
    scraped_links = crawl_links()
    cached_links = load_cache()
    new_links = [l for l in scraped_links if l not in cached_links]

    if new_links:
        batch_size = 20
        for i in range(0, len(new_links), batch_size):
            batch_links = new_links[i:i+batch_size]
            message = "*JB Hi-Fi Pokémon Products (New)*\n\n" + "\n".join(batch_links)
            send_telegram_message(message)

        cached_links.update(new_links)
        save_cache(cached_links)
    else:
        logging.info("No new links to send.")

    return jsonify({
        "total_scraped": len(scraped_links),
        "new_links_sent": len(new_links),
        "links": scraped_links
    })

if __name__ == "__main__":
    logging.info("Starting Flask app on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
