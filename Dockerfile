FROM python:3.11-slim

WORKDIR /app

# Cài các thư viện Chromium cần thiết
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libglib2.0-0 libgobject-2.0-0 libexpat1 libdbus-1-3 libatspi2.0-0 \
    wget curl ca-certificates fonts-liberation --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Cài Chromium cho Playwright
RUN playwright install chromium

EXPOSE 5000

CMD ["python", "pokemon_scraper.py"]
