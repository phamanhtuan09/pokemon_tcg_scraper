import sys
import threading
import json
import os
import logging
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# =============== CONFIG ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_KEYWORDS = 'pokemon trading cards'
CACHE_FILE = 'cache.json'
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

logging.info(f"✅ Python {sys.version}")
logging.info(f"✅ TELEGRAM_TOKEN: {'✅ Loaded' if TELEGRAM_TOKEN else '❌ Missing'}")
logging.info(f"✅ TELEGRAM_CHAT_ID: {'✅ Loaded' if TELEGRAM_CHAT_ID else '❌ Missing'}")

# ============ TELEGRAM =====================

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("❌ Missing Telegram config.")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        )
        logging.info(f"📨 Telegram sent. Status: {resp.status_code}")
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")

# ============= SCRAPER =====================

def get_html_with_retry(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"🌐 Fetching: {url} (Attempt {attempt})")
            res = requests.get(url, headers=HEADERS, timeout=15)
            res.raise_for_status()
            return res.text
        except Exception as e:
            logging.warning(f"⚠️ Attempt {attempt} failed: {e}")
            time.sleep(2)
    logging.error(f"❌ Failed to fetch after {MAX_RETRIES} attempts: {url}")
    return ""

def scrape_site(name, url, selector, prefix, keyword="pokemon"):
    logging.info(f"🔍 Scraping {name}")
    html = get_html_with_retry(url)
    if not html:
        logging.warning(f"⚠️ No HTML for {name}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    links = [
        prefix + a['href'] if not a['href'].startswith("http") else a['href']
        for a in soup.select(selector)
        if 'href' in a.attrs and keyword.lower() in a['href'].lower()
    ]
    unique_links = list(set(links))
    logging.info(f"🔗 {name}: {len(unique_links)} links found")
    return unique_links

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE) as f:
        return json.load(f)

def save_cache(data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

def run_scraper():
    logging.info("🚀 Starting scraper")
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
        },
        "Zingpopculture": {
            "url": f"https://www.zingpopculture.com/search?q={SEARCH_KEYWORDS.replace(' ', '+')}",
            "selector": "a.product-item-link",
            "prefix": "https://www.zingpopculture.com"
        },
        "Toymate": {
            "url": f"https://www.toymate.com.au/search?q={SEARCH_KEYWORDS.replace(' ', '+')}",
            "selector": "a.product-title",
            "prefix": "https://www.toymate.com.au"
        }
    }

    for site, conf in sites.items():
        links = scrape_site(site, conf['url'], conf['selector'], conf['prefix'])
        old = cache.get(site, [])
        new = [l for l in links if l not in old]

        if new:
            found_links.append(f"*{site}*\n" + "\n".join(new))
        new_cache[site] = list(set(old + links))

    if found_links:
        message = "🧩 *New Pokémon TCG Products:*\n\n" + "\n\n".join(found_links)
        send_telegram_message(message)
    else:
        logging.info("ℹ️ No new links found.")

    save_cache(new_cache)
    logging.info("✅ Scraper finished.")

# ============= HTTP ENDPOINTS ==============

@app.route("/run", methods=["GET"])
def run():
    logging.info("🔁 /run endpoint triggered.")
    threading.Thread(target=run_scraper).start()
    return "Scraper started!", 200

@app.route("/")
def home():
    return "🟢 Pokemon Scraper Bot is running."

# ================ MAIN ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
