import sys
import os
import json
import logging
import asyncio
import httpx
from fastapi import FastAPI
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup

app =  FastAPI()

# =============== CONFIG ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_KEYWORDS = 'pokemon trading cards'
CACHE_FILE = 'cache.json'
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_RETRIES = 3
BROWSER_PROFILE_DIR = "/app/browser_profile"  # Lưu session/tiết kiệm recheck Cloudflare

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logging.info(f"✅ Python {sys.version}")
logging.info(f"✅ TELEGRAM_TOKEN: {'✅ Loaded' if TELEGRAM_TOKEN else '❌ Missing'}")
logging.info(f"✅ TELEGRAM_CHAT_ID: {'✅ Loaded' if TELEGRAM_CHAT_ID else '❌ Missing'}")

# ============ TELEGRAM =====================

async def send_telegram_message(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("❌ Missing Telegram config.")
        return
    try:
        async with httpx.AsyncClient() as client:
            resp =await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                },
                timeout = 20
            ) 
        logging.info(f"📨 Telegram sent. Status: {resp.status_code}")
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")

async def send_file_to_telegram(file_path: str, caption: str = "File"):
    """
    Gửi file qua Telegram Bot (async)
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("❌ Missing Telegram config.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f)}
                data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
                resp = await client.post(url, data=data, files=files)
                resp.raise_for_status()
                logging.info(f"📨 Telegram file sent: {file_path}")
                return resp.json()
    except Exception as e:
        logging.error(f"❌ Failed to send file to Telegram: {e}")
        return None

# ============= SCRAPER =====================

async def get_html_with_retry(url: str) -> str:
    async with httpx.AsyncClient() as client:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logging.info(f"🌐 Fetching: {url} (Attempt {attempt})")
                res = await client.get(url, headers=HEADERS, timeout=15)
                res.raise_for_status()
                return res.text
            except Exception as e:
                logging.warning(f"⚠️ Attempt {attempt} failed: {e}")
                await asyncio.sleep(2)
    logging.error(f"❌ Failed to fetch after {MAX_RETRIES} attempts: {url}")
    return ""

async def scrape_site(name, url, selector, prefix, keyword="pokemon"):
    logging.info(f"🔍 Scraping {name}")
    html = await get_html_with_retry(url)
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

async def scrape_jbhifi_playwright(proxy: str = None):
    logging.info("🔍 Scraping JB Hi-Fi with Playwright")
    url = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"

    links = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                    "--disable-background-networking"
                ],
                proxy={"server": proxy} if proxy else None
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1024, "height": 768},
                java_script_enabled=True,
                bypass_csp=True,
                record_har_path=None,
                user_data_dir=BROWSER_PROFILE_DIR
            )
            page = await context.new_page()
            await stealth_async(page)

            # Optional: block images/fonts for faster load
            await page.route(
                "**/*",
                lambda route: asyncio.create_task(
                    route.abort() if route.request.resource_type in ["image", "stylesheet", "font"] else route.continue_()
                )
            )

            logging.info(f"🌐 Opening {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Fake user behavior: scroll + wait
            await page.mouse.move(100, 100)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(5000)  # đợi AJAX load xong
            
            # Chờ selector sản phẩm
            try:
                await page.wait_for_selector("a[href*='/products/']", timeout=15000)
            except Exception:
                html = await page.content()
                file_path = "jb_debug.html"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html)
                logging.warning(f"⚠️ Selector not found, saved HTML snapshot to {file_path}")
                try:
                    await send_file_to_telegram(file_path, caption="JB Hi-Fi snapshot")
                except Exception:
                    pass
                raise Exception("⚠️ Could not find product links. Possibly blocked by Cloudflare.")

            # Lấy tất cả product links
            a_tags = await page.query_selector_all("a[href*='/products/']")
            for a in a_tags:
                href = await a.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        href = "https://www.jbhifi.com.au" + href
                    links.append(href)

            logging.info(f"🔗 JB Hi-Fi (Playwright): {len(links)} links found")
            await context.close()
            await browser.close()
            return list(set(links))

    except Exception as e:
        logging.error(f"❌ JB Hi-Fi Playwright error: {e}")
        return []

def scrape_jbhifi_requests():
    url = "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        product_links = [a["href"] for a in soup.select("a[href*='/products/']") if a.get("href")]
        product_links = ["https://www.jbhifi.com.au" + l if l.startswith("/") else l for l in product_links]
        return list(set(product_links))
    except Exception as e:
        logging.error(f"❌ JB Hi-Fi requests fallback error: {e}")
        return []

async def scrape_jbhifi_combined(proxy: str = None):
    links = await scrape_jbhifi_playwright(proxy=proxy)
    if not links:
        logging.info("⚠️ Playwright failed, using requests fallback")
        links = scrape_jbhifi_requests()
    return links

# def scrape_kmart():
#     logging.info("🔍 Scraping Kmart")
#     url = "https://www.kmart.com.au/category/toys/pokemon-trading-cards/"
#     html = get_html_with_retry(url)
#     if not html:
#         logging.warning("⚠️ No HTML for Kmart")
#         return []

#     soup = BeautifulSoup(html, 'html.parser')
#     # Selector sản phẩm Kmart hiện tại
#     product_links = []
#     for a in soup.select('a.product-card__link'):
#         href = a.get('href')
#         if href:
#             if href.startswith('/'):
#                 href = 'https://www.kmart.com.au' + href
#             product_links.append(href)
#     unique_links = list(set(product_links))
#     logging.info(f"🔗 Kmart: {len(unique_links)} links found")
#     return unique_links

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE) as f:
        return json.load(f)

def save_cache(data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

async def run_scraper():
    logging.info("🚀 Starting scraper")
    cache = load_cache()
    new_cache = {}
    found_links = []

    # Các trang web
    sites = {
        "JB Hi-Fi": {"func": lambda: scrape_jbhifi_combined(proxy=None)},
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
            links = await conf["func"]()
        else:
            links = await scrape_site(site, conf['url'], conf['selector'], conf['prefix'])

        old = set(cache.get(site, []))
        current = set(links)
        new = current - old

        if new:
            formatted_links = "\n".join(sorted(new))
            found_links.append(f"*{site}*\n{formatted_links}")
        new_cache[site] = list(set(current | old))

    if found_links:
        message = "🧩 *New Pokémon TCG Products:*\n\n" + "\n\n".join(found_links)
        await send_telegram_message(message)
    else:
        logging.info("ℹ️ No new links found.")

    save_cache(new_cache)
    logging.info("✅ Scraper finished.")

# ============= HTTP ENDPOINTS ==============

@app.get("/")
async def home():
    return { "status": "🟢 Pokemon Scraper Bot is running." }

@app.get("/run")
async def run():
    logging.info("🔁 /run endpoint triggered.")
    asyncio.create_task(run_scraper())
    return { "message": "Scraper started!" }

# ================ MAIN ======================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
