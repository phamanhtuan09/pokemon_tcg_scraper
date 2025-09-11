# Base image nhẹ hơn thay vì full playwright
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Cài các thư viện hệ thống mà Chromium cần + công cụ cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libc6 \
    libcups2 \
    libdrm2 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy dependency file và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers (chromium) matching package version
RUN playwright install --with-deps chromium

# Copy toàn bộ mã nguồn vào image
COPY . .

# Mở port cho Flask app
EXPOSE 10000

# Khởi động app
CMD ["uvicorn", "pokemon_scraper:app", "--host", "0.0.0.0", "--port", "10000"]
