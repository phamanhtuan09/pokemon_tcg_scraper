# Dùng python slim
FROM python:3.11-slim

# ---------------- Step 1: cài các dependencies tối thiểu cho Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libxss1 \
    libxcursor1 \
    libxinerama1 \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------- Step 2: copy requirements và install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------- Step 3: copy source
COPY . .

# ---------------- Step 4: set môi trường cho Pyppeteer
ENV PYPPETEER_HOME=/app/.pyppeteer
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

# Pyppeteer sẽ cài Chromium tại /app/.pyppeteer
RUN python -m pyppeteer install --local

# ---------------- Step 5: expose port và CMD
EXPOSE 5000
CMD ["python", "pokemon_scraper.py"]
