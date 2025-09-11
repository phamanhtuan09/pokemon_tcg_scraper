# ---------------- Build stage ----------------
FROM python:3.11-slim AS builder

# Cài pip packages
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# ---------------- Runtime stage ----------------
FROM python:3.11-slim

# Cài Chromium + thư viện runtime cho Pyppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    libx11-xcb1 \
    libxshmfence1 \
    libxrender1 \
    libxi6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pip + source code từ stage build
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Cho Pyppeteer biết path Chromium system
ENV PYPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PYPPETEER_HOME=/root/.pyppeteer

EXPOSE 5000

CMD ["python", "pokemon_scraper.py"]
