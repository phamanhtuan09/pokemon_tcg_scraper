# ---------------- Stage 1: Build ----------------
FROM python:3.12-slim AS builder

# Cài hệ thống cơ bản + Chromium
RUN apt-get update && apt-get install -y \
    chromium \
    wget \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements và cài pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------- Stage 2: Final ----------------
FROM python:3.12-slim

# Copy Chromium từ builder
COPY --from=builder /usr/bin/chromium /usr/bin/chromium
COPY --from=builder /usr/lib/chromium/ /usr/lib/chromium/

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

# Set executable path cho Pyppeteer
ENV PYPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV SAVE_HTML_SNAPSHOT=1

EXPOSE 5000
CMD ["python", "pokemon_scraper.py"]
