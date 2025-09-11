# ---------------- Build stage ----------------
FROM python:3.11-slim AS builder

# Cài đặt dependencies build + Chromium dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    gnupg \
    ca-certificates \
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

# Copy requirements.txt first để cache pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài Pyppeteer + tải Chromium
RUN python -m pyppeteer install --local

# Copy source code
COPY . .

# ---------------- Runtime stage ----------------
FROM python:3.11-slim

# Cài dependencies runtime tối thiểu cho Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Copy pip + Pyppeteer + Chromium từ stage build
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app /app

# Set environment variable Pyppeteer biết path Chromium
ENV PYPPETEER_HOME=/root/.local

EXPOSE 5000

CMD ["python", "pokemon_scraper.py"]
