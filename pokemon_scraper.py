import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import time
import logging
import sys
import json
import os

# ----------------- CONFIG -----------------
MAX_RETRIES = 3
TELEGRAM_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # <-- Thay bằng token bot Telegram của bạn
TELEGRAM_CHAT_ID = 'YOUR_CHAT_ID'           # <-- Thay bằng chat ID cá nhân của bạn
SEARCH_KEYWORDS = 'pokemon trading cards'
HEADLESS = True  # Để True khi chạy bằng cron hoặc server

CACHE_FILE = 'cache.json'

# ----------------- LOGGING -----------------
logging.basicConfig(
    filename='scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------- TELEGRAM -----------------
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

# ----------------- SELENIUM SETUP -----------------
def get_driver():
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    try:
        return webdriver.Chrome(options=options)
    except WebDriverException as e:
        logging.error(f"Selenium driver error: {e}")
        sys.exit(1)

# ----------------- REQUEST WRAPPER -----------------
def get_with_retry(url, use_selenium=False):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if use_selenium:
                driver = get_driver()
                driver.get(url)
                time.sleep(5)
                page = driver.page_source
                driver.quit()
                return page
            else:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logging.warning(f"[{attempt}/{MAX_RETRIES}] Failed to get {url}: {e}")
            time.sleep(2)
    return None

# ----------------- SCRAPERS -----------------
def scrape_jbhifi():
    url = f"https://www.jbhifi.com.au/search?query={SEARCH_KEYWORDS.replace(' ', '%20')}"
    html = get_with_retry(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = [
        "https://www.jbhifi.com.au" + a.get("href")
        for a in soup.select(".ais-InfiniteHits-item a")
        if a.get("href") and "pokemon" in a.get("href").lower()
    ]
    return list(set(links))

def scrape_kmart():
    url = f"https://www.kmart.com.au/search/?q={SEARCH_KEYWORDS.replace(' ', '%20')}"
    html = get_with_retry(url, use_selenium=True)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = [
        "https://www.kmart.com.au" + a.get("href")
        for a in soup.select("a[href]")
        if "/product/" in a.get("href") and "pokemon" in a.get("href").lower()
    ]
    return list(set(links))

def scrape_target():
    url = f"https://www.target.com.au/search?text={SEARCH_KEYWORDS.replace(' ', '+')}"
    html = get_with_retry(url, use_selenium=True)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = [
        "https://www.target.com.au" + a.get("href")
        for a in soup.select("a[href]")
        if "/p/" in a.get("href") and "pokemon" in a.get("href").lower()
    ]
    return list(set(links))

def scrape_bigw():
    url = f"https://www.bigw.com.au/search?q={SEARCH_KEYWORDS.replace(' ', '%20')}"
    html = get_with_retry(url, use_selenium=True)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = [
        "https://www.bigw.com.au" + a.get("href")
        for a in soup.select("a[href]")
        if "/product/" in a.get("href") and "pokemon" in a.get("href").lower()
    ]
    return list(set(links))

# ----------------- CACHE -----------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

# ----------------- MAIN -----------------
def main():
    try:
        all_links = {
            "JB Hi-Fi": scrape_jbhifi(),
            "Kmart": scrape_kmart(),
            "Target": scrape_target(),
            "Big W": scrape_bigw()
        }

        cache = load_cache()
        new_cache = {}
        message = "🧩 *Pokémon TCG - New Products Found:*\n\n"
        found = False

        for site, links in all_links.items():
            new_links = []
            old_links = cache.get(site, [])
            for link in links:
                if link not in old_links:
                    new_links.append(link)

            if new_links:
                found = True
                message += f"*{site}*\n" + "\n".join(new_links) + "\n\n"

            new_cache[site] = list(set(old_links + links))

        if found:
            send_telegram_message(message)
            logging.info("New products sent to Telegram.")
        else:
            logging.info("No new products found.")

        save_cache(new_cache)

    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")
        send_telegram_message(f"❗ Bot Error: {e}")

if __name__ == "__main__":
    main()
