# Base image nhẹ hơn thay vì full playwright
FROM python:3.11-slim as base

# Cài các dependency bắt buộc để Chromium chạy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxrandr2 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libgbm1 libgtk-3-0 libxshmfence1 \
    wget unzip curl fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Cài playwright + chromium
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

# Set workdir
WORKDIR /app

# Copy dependency file và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào image
COPY . .

# Mở port cho Flask app
EXPOSE 10000

# Khởi động app
CMD ["uvicorn", "pokemon_scraper:app", "--host", "0.0.0.0", "--port", "10000"]
