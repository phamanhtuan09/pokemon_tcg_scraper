# ✅ Dùng image chính thức của Playwright có Chromium pre-installed
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

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
CMD ["python", "pokemon_scraper.py"]
