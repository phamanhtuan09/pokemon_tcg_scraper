FROM python:3.10-slim

# Cài đặt các package cần thiết để chạy Chromium
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libxshmfence1 libxfixes3 libxcursor1 libxext6 libxrender1 libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Cài browser cho Playwright
RUN python -m playwright install chromium

COPY . /app

EXPOSE 10000

CMD ["python", "pokemon_scraper.py"]
