"""
GMGN Scraper - Konfigürasyon Dosyası
Telegram bot token ve grup ID'nizi buraya girin.
"""

# ==================== TELEGRAM AYARLARI ====================
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# ==================== GMGN CHAIN URL'LERI ====================
# Her komut için ayrı URL tanımlayın
# Sistem sadece Ethereum uzerinden calisir.
# /eth -> Ethereum
CHAINS = {
    "eth": "https://gmgn.ai/?chain=eth",
}

# ==================== GMGN API AYARLARI ====================
GMGN_BASE_URL = "https://gmgn.ai/defi/quotation/v1/rank"
GMGN_TIME_PERIOD = "1h"  # 1m, 5m, 1h, 6h, 24h
GMGN_ORDER_BY = "open_timestamp"  # En son çıkan token ilk sırada
GMGN_DIRECTION = "desc"  # desc = en yeniden eskiye
GMGN_FILTERS = ["not_honeypot", "verified", "renounced"]

# ==================== SCRAPER AYARLARI ====================
REQUEST_TIMEOUT = 8  # saniye
MAX_RETRIES = 1
RETRY_BACKOFF = 0.3  # saniye
MAX_TOKENS_TO_SHOW = 20  # Telegram'a gönderilecek max token sayısı

# ==================== TELEGRAM BOT AYARLARI ====================
TELEGRAM_POLL_TIMEOUT = 20  # getUpdates long-poll suresi
TELEGRAM_SEND_TIMEOUT = 8  # mesaj gonderme timeout'u
COMMAND_WORKERS = 4  # ayni anda calisabilecek komut sayisi
INSTANCE_LOCK_HOST = "127.0.0.1"
INSTANCE_LOCK_PORT = 28777  # ayni botun iki kez acilmasini engeller

# ==================== OTOMATIK TOKEN BILDIRIMLERI ====================
AUTO_NOTIFY_ENABLED = True
AUTO_NOTIFY_CHAINS = ["eth"]
AUTO_NOTIFY_INTERVAL_SECONDS = 30
AUTO_NOTIFY_MAX_TOKENS_PER_CYCLE = 10
AUTO_NOTIFY_STATE_FILE = "data/notified_tokens.json"
AUTO_NOTIFY_STATE_KEEP_LIMIT = 5000

# ==================== FIYAT TAKIP BILDIRIMLERI ====================
PRICE_TRACK_ENABLED = True
PRICE_TRACK_INTERVAL_SECONDS = 20
PRICE_TRACK_MAX_TOKENS_PER_COMMAND = 20
PRICE_TRACK_MIN_CHANGE_PERCENT = 1.0
PRICE_TRACK_COOLDOWN_SECONDS = 60

# ==================== DOSYA AYARLARI ====================
DATA_DIR = "data"
JSON_OUTPUT_FILE = "data/gmgn_tokens.json"

# ==================== LOGLAMA ====================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
