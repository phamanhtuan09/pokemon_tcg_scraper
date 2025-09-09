import sys
print(f"✅ Running Python version: {sys.version}")

import threading
import json
import os
import logging
import time
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from flask import Flask

app = Flask(__name__)

# =================== CONFIG ===================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_KEYWORDS = 'pokemon trading cards'
CACHE_FILE = 'cache.json'
HEADLESS = True
MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

logging.info(f"✅ Starting scraper with Python {sys.version}")
logging.info(f"✅ TELEGRAM_CHAT_ID: {'✅ Loaded' if TELEGRAM_CHAT_ID else '❌ Missing'}")
logging.info(f"✅ TELEGRAM_TOKEN: {'✅ Loaded' if TELEGRAM_TOKEN else '❌ Missing'}")

# ================ UTILS =====================

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("❌ Missing Telegram configuration.")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        )
        logging.info(f"📨 Telegram sent. Status: {resp.status_code}, Response: {resp.text}")
    except Exception as e:
        logging.error(f"Telegram error: {e}")

def get_driver():
    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Đảm bảo Chrome chạy đúng trên Render
    options.binary_location = "/usr/bin/chromium-browser"

    logging.info("🚗 Initializing Chrome driver...")
    try:
        driver = uc.Chrome(options=options)
        return driver
    except Exception as e:
        logging.error(f"❌ Failed to initialize Chrome: {e}")
        raise

def get_with_retry(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"🌐 Getting URL (Attempt {attempt}): {url}")
            driver = get_driver()
            driver.get(url)
            time.sleep(5)
            html = driver.page_source
            driver.quit()
            logging.info(f"✅ Successfully got HTML from: {url}")
            return html
        except Exception as e:
            logging.warning(f"⚠️ Retry {attempt}: {e}")
            time.sleep(2)
    logging.error(f"❌ Failed to fetch URL after {MAX_RETRIES} attempts: {url}")
    return ""

def scrape_site(name, url, selector, prefix, keyword='pokemon'):
    logging.info(f"🔍 Scraping site: {name}")
    html = get_with_retry(url)
    if not html:
        logging.warning(f"⚠️ No HTML received for {name}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = list(set(
        prefix + a['href']
        for a in soup.select(selector)
        if 'href' in a.attrs and keyword in a['href'].lower()
    ))

    logging.info(f"🔗 Found {len(links)} links on {name}")
    return links

def load_cache():
    if not os.path.exists(CACHE_FILE):
        logging.info("📁 No cache file found. Starting fresh.")
        return {}
    with open(CACHE_FILE) as f:
        cache = json.load(f)
        logging.info(f"📦 Loaded cache: {sum(len(v) for v in cache.values())} total links")
        return cache

def save_cache(data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)
    logging.info(f"💾 Cache saved with {sum(len(v) for v in data.values())} total links")

def run_scraper():
    logging.info("🚀 Running scraper...")

    cache = load_cache()
    new_cache = {}
    found_links = []
    sites = {
        "JB Hi-Fi": {
            "url": f"https://www.jbhifi.com.au/search?query={SEARCH_KEYWORDS.replace(' ', '%20')}",
            "selector": ".ais-InfiniteHits-item a",
            "prefix": "https://www.jbhifi.com.au"
        },
        "Kmart": {
            "url": f"https://www.kmart.com.au/search/?q={SEARCH_KEYWORDS.replace(' ', '%20')}",
            "selector": "a[href*='/product/']",
            "prefix": "https://www.kmart.com.au"
        },
        "Target": {
            "url": f"https://www.target.com.au/search?text={SEARCH_KEYWORDS.replace(' ', '+')}",
            "selector": "a[href*='/p/']",
            "prefix": "https://www.target.com.au"
        },
        "Big W": {
            "url": f"https://www.bigw.com.au/search?q={SEARCH_KEYWORDS.replace(' ', '%20')}",
            "selector": "a[href*='/product/']",
            "prefix": "https://www.bigw.com.au"
        }
    }

    for site, conf in sites.items():
        links = scrape_site(site, conf['url'], conf['selector'], conf['prefix'])
        old = cache.get(site, [])
        new = [l for l in links if l not in old]

        logging.info(f"➕ {site}: {len(new)} new links")

        if new:
            found_links.append(f"*{site}*\n" + "\n".join(new))
        new_cache[site] = list(set(old + links))

    if found_links:
        message = "🧩 *New Pokémon TCG Products:*\n\n" + "\n\n".join(found_links)
        send_telegram_message(message)
    else:
        logging.info("ℹ️ No new links found.")

    save_cache(new_cache)
    logging.info("✅ Scraper run complete.")

# ============= HTTP ENDPOINTS ==============

@app.route("/run", methods=["GET"])
def run():
    logging.info("🔁 /run endpoint triggered.")
    threading.Thread(target=run_scraper).start()
    return "Scraper started!", 200

@app.route("/")
def home():
    return "🟢 Pokemon Scraper Bot is running."

# ================ MAIN =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
