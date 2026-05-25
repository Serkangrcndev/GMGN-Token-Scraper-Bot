"""
Telegram Bot - Chain komutlarıyla scraper'ı çalıştırır.
Komutlar: /eth, /help
"""

import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock

from services.scraper_service import ScraperService
from services.price_monitor import PriceMonitor
from services.token_monitor import NewTokenMonitor
import config

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.scraper_service = ScraperService()
        self.last_update_id = 0
        self.executor = ThreadPoolExecutor(
            max_workers=getattr(config, "COMMAND_WORKERS", 4),
            thread_name_prefix="telegram-command",
        )
        self.active_commands = set()
        self.active_commands_lock = Lock()
        self.monitor = None
        self.price_monitor = None

    def send_message(self, text, chat_id=None, parse_mode=None):
        """Telegram'a mesaj gönder. Uzun mesajları otomatik böler."""
        chat_id = chat_id or self.chat_id
        url = f"{self.base_url}/sendMessage"

        max_length = 4000
        messages = []

        if len(text) <= max_length:
            messages.append(text)
        else:
            lines = text.split("\n")
            current_chunk = ""
            for line in lines:
                if len(current_chunk) + len(line) + 1 > max_length:
                    messages.append(current_chunk)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"
            if current_chunk:
                messages.append(current_chunk)

        results = []
        for msg in messages:
            payload = {"chat_id": chat_id, "text": msg}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=getattr(config, "TELEGRAM_SEND_TIMEOUT", 8),
                )
                result = response.json()
                if not result.get("ok"):
                    logger.error(f"Mesaj hatasi: {result.get('description')}")
                results.append(result)
            except Exception as e:
                logger.error(f"Telegram API hatasi: {str(e)}")
                results.append({"ok": False, "error": str(e)})

        return results

    def get_updates(self):
        """Yeni mesajları kontrol et (long polling - anında yanıt)"""
        url = f"{self.base_url}/getUpdates"
        poll_timeout = getattr(config, "TELEGRAM_POLL_TIMEOUT", 20)
        params = {"offset": self.last_update_id + 1, "timeout": poll_timeout}

        try:
            response = requests.get(url, params=params, timeout=poll_timeout + 5)
            data = response.json()
            if data.get("ok"):
                results = data.get("result", [])
                if results:
                    logger.info(f"{len(results)} yeni mesaj alindi.")
                return results
            logger.error(f"Updates hatasi: {data.get('description')}")
            return []
        except Exception as e:
            logger.error(f"Updates hatasi: {str(e)}")
            return []

    def queue_chain(self, chain, chat_id):
        """Run chain commands in the background so polling stays responsive."""
        command_key = (chat_id, chain)
        with self.active_commands_lock:
            if command_key in self.active_commands:
                self.send_message(
                    f"/{chain} zaten calisiyor, bitince sonucu gonderecegim.",
                    chat_id=chat_id,
                )
                return
            self.active_commands.add(command_key)

        self.executor.submit(self._run_chain_job, chain, chat_id, command_key)

    def _run_chain_job(self, chain, chat_id, command_key):
        try:
            self.handle_chain(chain, chat_id)
        finally:
            with self.active_commands_lock:
                self.active_commands.discard(command_key)

    def handle_chain(self, chain, chat_id):
        """
        Chain komutu handler'ı. /{chain} yazılınca o chain'in verilerini çeker.
        """
        chain_url = config.CHAINS.get(chain, "")

        self.send_message(
            f"GMGN.ai Scraper baslatiliyor...\n"
            f"Chain: {chain.upper()}\n"
            f"URL: {chain_url}\n"
            f"Siralama: En yeni token ilk sirada\n"
            f"Lutfen bekleyin...",
            chat_id=chat_id,
        )

        # Scraper'ı çalıştır
        scraper_service = ScraperService()
        result = scraper_service.fetch_and_save(chain)

        if result["success"]:
            tokens = result["tokens"]

            # Formatlanmış mesajı gönder
            message = scraper_service.format_token_message(tokens, chain)
            self.send_message(message, chat_id=chat_id)

            # Özet
            summary = (
                f"Islem tamamlandi!\n"
                f"Chain: {chain.upper()}\n"
                f"Token sayisi: {result['token_count']}\n"
                f"Sure: {result['duration']}s\n"
                f"JSON: {result['json_path']}"
            )
            if self.price_monitor:
                watched_count = self.price_monitor.watch_tokens(chain, tokens, chat_id)
                if watched_count:
                    summary += (
                        f"\nFiyat takibi: {watched_count} token izleniyor "
                        f"(esik: %{config.PRICE_TRACK_MIN_CHANGE_PERCENT})"
                    )
            self.send_message(summary, chat_id=chat_id)
            logger.info(f"/{chain} komutu basarili. {result['token_count']} token.")
        else:
            self.send_message(f"Hata: {result.get('error')}", chat_id=chat_id)
            logger.error(f"/{chain} basarisiz: {result.get('error')}")

    def handle_start(self, chat_id):
        """/start komutu - Karşılama ve komut listesi"""
        chains = self.scraper_service.get_available_chains()
        chain_list = "\n".join([f"  /{c} - {c.upper()} token'lari cek" for c in chains])

        msg = (
            "GMGN Token Scraper Bot'a hosgeldiniz!\n"
            "============================\n\n"
            "Kullanilabilir komutlar:\n"
            f"{chain_list}\n\n"
            "  /start - Bu mesaji goster\n"
            "  /help - Yardim\n\n"
            "Bir chain secin ve token verilerini cekin!\n"
            "Veriler en yeni token ilk sirada olacak sekilde siralanir.\n"
            "ETH yeni token bildirimleri otomatik aciktir."
        )
        self.send_message(msg, chat_id=chat_id)

    def handle_help(self, chat_id):
        """/help komutu"""
        chains = self.scraper_service.get_available_chains()
        chain_list = "\n".join([f"  /{c} -> {config.CHAINS[c]}" for c in chains])

        help_msg = (
            "GMGN Token Scraper Bot - Yardim\n"
            "================================\n\n"
            "Desteklenen chain komutlari:\n"
            f"{chain_list}\n\n"
            "Her komut ilgili chain'deki en yeni token'lari\n"
            "ceker, JSON'a kaydeder ve size gonderir.\n\n"
            "Otomatik bildirim: ETH yeni token'lari\n"
            "komut beklemeden gruba gonderilir.\n"
            "Fiyat takibi: Chain komutundan sonra listelenen tokenlar\n"
            "fiyat degisimi icin otomatik izlenir.\n\n"
            "Config'den yeni chain ekleyebilirsiniz:\n"
            "  config.py -> CHAINS sozlugune ekleyin."
        )
        self.send_message(help_msg, chat_id=chat_id)

    def process_update(self, update):
        """Gelen update'i işle"""
        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")

        if not text or not chat_id:
            return

        # Komut kontrolü
        if text == "/start":
            self.handle_start(chat_id)
        elif text == "/help":
            self.handle_help(chat_id)
        elif text.startswith("/"):
            # /{chain} komutunu kontrol et
            chain = text[1:].lower()  # /eth -> eth
            if chain in config.CHAINS:
                self.queue_chain(chain, chat_id)
            else:
                available = ", ".join([f"/{c}" for c in config.CHAINS.keys()])
                self.send_message(
                    f"Bilinmeyen komut: {text}\n"
                    f"Kullanilabilir: {available}",
                    chat_id=chat_id,
                )

    def delete_webhook(self):
        """Mevcut webhook ve eski oturumları tamamen temizle"""
        import time

        # 1. Bot oturumunu kapat (sunucu tarafındaki bağlantıyı keser)
        try:
            requests.post(f"{self.base_url}/close", timeout=10)
            logger.info("Bot oturumu kapatildi.")
        except:
            pass

        time.sleep(2)

        # 2. Webhook sil
        try:
            requests.post(
                f"{self.base_url}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=10,
            )
            logger.info("Webhook silindi.")
        except:
            pass

        time.sleep(2)

        # 3. Son update ID'yi al
        try:
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params={"offset": -1, "timeout": 0},
                timeout=10,
            )
            data = response.json()
            if data.get("ok") and data.get("result"):
                self.last_update_id = data["result"][-1]["update_id"]
                logger.info(f"Son update_id: {self.last_update_id}")
        except:
            pass

        logger.info("Bot hazir, komut bekleniyor.")

    def start_monitor(self):
        """Start ETH new-token notifications in the background."""
        if not getattr(config, "AUTO_NOTIFY_ENABLED", True):
            logger.info("Auto notify monitor kapali.")
        else:
            self.monitor = NewTokenMonitor(self.send_message)
            self.monitor.start()

        if not getattr(config, "PRICE_TRACK_ENABLED", True):
            logger.info("Price monitor kapali.")
        else:
            self.price_monitor = PriceMonitor(self.send_message)
            self.price_monitor.start()

    def shutdown(self):
        """Stop background workers cleanly."""
        if self.monitor:
            self.monitor.stop()
        if self.price_monitor:
            self.price_monitor.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def run(self):
        """Bot'u long-polling modunda çalıştır"""
        self.delete_webhook()
        self.start_monitor()

        chains = ", ".join([f"/{c}" for c in config.CHAINS.keys()])
        logger.info("Telegram Bot baslatildi.")
        print("=" * 50)
        print("  GMGN Token Scraper Bot Aktif")
        print(f"  Komutlar: {chains}, /help")
        print("=" * 50)
        print("Bot calisiyor... Durdurmak icin CTRL+C basin.\n")

        try:
            while True:
                updates = self.get_updates()
                for update in updates:
                    update_id = update.get("update_id", 0)
                    if update_id > self.last_update_id:
                        self.last_update_id = update_id
                        self.process_update(update)

        except KeyboardInterrupt:
            logger.info("Bot durduruldu.")
            print("\nBot durduruldu.")
        except Exception as e:
            logger.error(f"Bot dongusu hatasi: {str(e)}")
            import time
            time.sleep(5)
        finally:
            self.shutdown()
