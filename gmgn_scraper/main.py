"""
GMGN Token Scraper - Ana Çalıştırma Dosyası
Telegram botu başlatır ve /start komutuyla scraper'ı tetikler.

Kullanım:
    python main.py
"""

import sys
import os
import logging
import socket

# Proje kök dizinini path'e ekle
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

import config
from bot.telegram_bot import TelegramBot


def setup_logging():
    """Loglama ayarlarını yapılandır"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("scraper.log", encoding="utf-8"),
        ],
    )


def validate_config():
    """Konfigürasyon değerlerini kontrol et"""
    errors = []

    if config.TELEGRAM_BOT_TOKEN == "BURAYA_BOT_TOKENINIZI_GIRIN":
        errors.append("TELEGRAM_BOT_TOKEN ayarlanmamis! config.py dosyasini duzenleyin.")

    if config.TELEGRAM_CHAT_ID == "BURAYA_GRUP_ID_GIRIN":
        errors.append("TELEGRAM_CHAT_ID ayarlanmamis! config.py dosyasini duzenleyin.")

    if errors:
        print("\n[!] KONFIGURASYON HATALARI:")
        for err in errors:
            print(f"    - {err}")
        print("\nLutfen config.py dosyasini duzenleyin ve tekrar deneyin.\n")
        sys.exit(1)


def acquire_instance_lock():
    """Tek bot instance'i calissin; Telegram getUpdates conflict'i engeller."""
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)

    try:
        lock_socket.bind((config.INSTANCE_LOCK_HOST, config.INSTANCE_LOCK_PORT))
        lock_socket.listen(1)
        return lock_socket
    except OSError:
        print(
            "\n[!] Bot zaten calisiyor gibi gorunuyor.\n"
            "    Ayni Telegram bot token'i ile iki program acik olursa komutlar gec gelir.\n"
            "    Eski pencereyi kapatip tekrar deneyin.\n"
        )
        sys.exit(1)


def main():
    """Ana fonksiyon"""
    # Loglama ayarla
    setup_logging()
    logger = logging.getLogger(__name__)

    # Konfigürasyon kontrolü
    validate_config()

    logger.info("GMGN Token Scraper baslatiliyor...")
    instance_lock = acquire_instance_lock()

    # Data klasörünü oluştur
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Telegram bot'u başlat
    try:
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Program kapatildi.")
    except Exception as e:
        logger.critical(f"Kritik hata: {str(e)}")
        sys.exit(1)
    finally:
        instance_lock.close()


if __name__ == "__main__":
    main()
