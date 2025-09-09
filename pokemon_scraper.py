import sys
import os
import json
import time
import logging
import asyncio
import threading
import requests
from flask import Flask
from playwright.sync_api import sync_playwright

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
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
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

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    links = [
        prefix + a['href'] if not a['href'].startswith("http") else a['href']
        for a in soup.select(selector)
        if 'href' in a.attrs and keyword.lower() in a['href'].lower()
    ]
    unique_links = list(set(links))
    logging.info(f"🔗 {name}: {len(unique_links)} links found")
    return unique_links

def scrape_jbhifi_playwright():
    logging.info("🔍 Scraping JB Hi-Fi with Playwright")
    url = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"

    links = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.70 Safari/537.36"
            )
            page = context.new_page()

            # Optional: block images/fonts for faster load
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "stylesheet", "font"] else route.continue_())

            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Đợi một chút nếu cần
            page.wait_for_timeout(2000)

            logging.info(f"🔍 JB Hi-Fi page HTML:\n{page[:3000]}")
            html = page.content()
            logging.info(f"🔍 JB Hi-Fi HTML:\n{html[:3000]}")  # chỉ log 3000 ký tự đầu


            # Tùy vào layout mới của JB Hi-Fi
            a_tags = page.query_selector_all("a[href*='/products/']")
            logging.info(f"🔍 JB Hi-Fi page HTML:\n{a_tags}")
            for a in a_tags:
                href = a.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = "https://www.jbhifi.com.au" + href
                    links.append(href)

            logging.info(f"🔗 JB Hi-Fi (Playwright): {len(links)} links found")
            context.close()
            browser.close()
            return list(set(links))

    except Exception as e:
        logging.error(f"❌ JB Hi-Fi Playwright error: {e}")
        return []

def scrape_kmart():
    logging.info("🔍 Scraping Kmart")
    url = "https://www.kmart.com.au/category/toys/pokemon-trading-cards/"
    html = get_html_with_retry(url)
    if not html:
        logging.warning("⚠️ No HTML for Kmart")
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    # Selector sản phẩm Kmart hiện tại
    product_links = []
    for a in soup.select('a.product-card__link'):
        href = a.get('href')
        if href:
            if href.startswith('/'):
                href = 'https://www.kmart.com.au' + href
            product_links.append(href)
    unique_links = list(set(product_links))
    logging.info(f"🔗 Kmart: {len(unique_links)} links found")
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

    # Các trang web
    sites = {
        "JB Hi-Fi": {"func": scrape_jbhifi_playwright},
        # "Kmart": {"func": scrape_kmart},
        "Target": {
            "url": f"https://www.target.com.au/search?text=trading+cards&group_id=W1852642",
            "selector": "a[href*='/p/']",
            "prefix": "https://www.target.com.au"
        },
        # "Big W": {
        #     "url": f"https://www.bigw.com.au/search?text={SEARCH_KEYWORDS.replace(' ', '+')}",
        #     "selector": "a[href*='/product/']",
        #     "prefix": "https://www.bigw.com.au"
        # },
        # "Zingpopculture": {
        #     "url": f"https://www.zingpopculture.com.au/search?attributes=franchise%3Apokemon&category=toys-hobbies&subcategory=toys-hobbies-trading-cards",
        #     "selector": "a.product-link",
        #     "prefix": "https://www.zingpopculture.com.au"
        # },
        # "Toymate": {
        #     "url": f"https://toymate.com.au/pokemon/?Product+Category=Trading+Cards",
        #     "selector": "a.product-item-link",
        #     "prefix": "https://www.toymate.com.au"
        # }
    }

    for site, conf in sites.items():
        if "func" in conf:
            links = conf["func"]()
        else:
            links = scrape_site(site, conf['url'], conf['selector'], conf['prefix'])
        old = cache.get(site, [])
        new = [l for l in links if l not in old]

        if new:
            formatted_links = "\n".join(new)
            found_links.append(f"*{site}*\n{formatted_links}")
        new_cache[site] = list(set(old + links))

    if found_links:
        message = "🧩 *New Pokémon TCG Products:*\n\n" + "\n\n".join(found_links)
        send_telegram_message(message)
    else:
        logging.info("ℹ️ No new links found.")

    save_cache(new_cache)
    logging.info("✅ Scraper finished.")

# ============= HTTP ENDPOINTS ==============

from flask import request

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
