# ---------------- Stage 1: Build ----------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
    wget \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------- Stage 2: Final ----------------
FROM python:3.12-slim

# Cài Chromium và các thư viện cần thiết
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-sandbox \
    fonts-liberation \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libxshmfence1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

# Set executable path cho Pyppeteer
ENV PYPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV SAVE_HTML_SNAPSHOT=1

EXPOSE 5000
CMD ["python", "pokemon_scraper.py"]
