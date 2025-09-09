# Pokemon TCG Scraper

## Mô tả
Scraper tự động lấy link sản phẩm Pokemon Trading Cards từ các trang JB Hi-Fi, Kmart, Target, Big W,... Gửi thông báo qua Telegram khi có sản phẩm mới.

## Cách chạy

### 1. Chuẩn bị biến môi trường
Tạo biến môi trường:

- `TELEGRAM_TOKEN` : Token bot Telegram
- `TELEGRAM_CHAT_ID` : Chat ID nhận tin nhắn

### 2. Build Docker image

```bash
docker build -t pokemon_tcg_scraper .
