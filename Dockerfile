FROM python:3.11-slim

# Cài đặt các dependency cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy requirements và cài đặt trước để cache docker tốt hơn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy toàn bộ source code
COPY . .

EXPOSE 5000

CMD ["python", "pokemon_scraper.py"]
