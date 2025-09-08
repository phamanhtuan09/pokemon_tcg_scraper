import sys
print(f"✅ Running Python version: {sys.version}")

from flask import Flask
import threading
import json
import os
import logging
import time
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_KEYWORDS = 'pokemon trading cards'
CACHE_FILE = 'cache.json'
HEADLESS = True
MAX_RETRIES = 3

logging.basicConfig(level=logging.INFO)

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Missing Telegram config.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message}
        )
    except Exception as e:
        logging.error(f"Telegram error: {e}")

def get_driver():
    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return uc.Chrome(options=options)

def get_with_retry(url):
    for attempt in range(MAX_RETRIES):
        try:
            driver = get_driver()
            driver.get(url)
            time.sleep(5)
            html = driver.page_source
            driver.quit()
            return html
        except Exception as e:
            logging.warning(f"Retry {attempt + 1}: {e}")
            time.sleep(2)
    return ""

def scrape_site(name, url, selector, prefix, keyword='pokemon'):
    html = get_with_retry(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    return list(set(
        prefix + a['href']
        for a in soup.select(selector)
        if 'href' in a.attrs and keyword in a['href'].lower()
    ))

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE) as f:
        return json.load(f)

def save_cache(data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

def run_scraper():
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
        if new:
            found_links.append(f"*{site}*\n" + "\n".join(new))
        new_cache[site] = list(set(old + links))

    if found_links:
        message = "🧩 *New Pokémon TCG Products:*\n\n" + "\n\n".join(found_links)
        send_telegram_message(message)

    save_cache(new_cache)

# HTTP endpoint to trigger scraper
@app.route("/run", methods=["GET"])
def run():
    threading.Thread(target=run_scraper).start()
    return "Scraper started!", 200

@app.route("/")
def home():
    return "🟢 Pokemon Scraper Bot is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
