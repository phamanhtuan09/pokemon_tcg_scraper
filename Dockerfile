# ---------------- Stage 1: Builder ----------------
FROM python:3.11-slim AS builder

# Cài dependencies cần thiết cho Chromium + Pyppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
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
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements & cài pip packages (cache tốt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài Chromium cho Pyppeteer
RUN python -m pyppeteer install --local

# Copy source code
COPY . .

# ---------------- Stage 2: Runtime ----------------
FROM python:3.11-slim

WORKDIR /app

# Copy pip packages từ builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Chromium cache & source code
COPY --from=builder /app /app

# Set Pyppeteer env
ENV PYPPETEER_HOME=/app/.pyppeteer
ENV PUPPETEER_EXECUTABLE_PATH=/app/.pyppeteer/chrome-linux/chrome

# Expose port
EXPOSE 5000

CMD ["python", "pokemon_scraper.py"]
