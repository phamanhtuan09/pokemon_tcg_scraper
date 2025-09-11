# Sử dụng Python 3.11 slim
FROM python:3.11-slim

# Đặt thư mục làm việc
WORKDIR /app

# Copy requirements và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code
COPY . .

# Expose cổng Flask
EXPOSE 5000

# Lệnh chạy app
CMD ["python", "app.py"]
