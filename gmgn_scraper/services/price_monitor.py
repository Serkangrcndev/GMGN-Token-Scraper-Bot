"""
Background price tracker for tokens requested with Telegram commands.
"""

import logging
import threading
import time

import config
from services.scraper_service import ScraperService

logger = logging.getLogger(__name__)


class PriceMonitor:
    def __init__(self, send_message):
        self.send_message = send_message
        self.scraper_service = ScraperService()
        self.interval = max(5, int(getattr(config, "PRICE_TRACK_INTERVAL_SECONDS", 20)))
        self.max_tokens = max(1, int(getattr(config, "PRICE_TRACK_MAX_TOKENS_PER_COMMAND", 20)))
        self.min_change_percent = max(
            0.0,
            float(getattr(config, "PRICE_TRACK_MIN_CHANGE_PERCENT", 1.0)),
        )
        self.cooldown = max(0, int(getattr(config, "PRICE_TRACK_COOLDOWN_SECONDS", 60)))
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.tracked = {}

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(
            target=self.run,
            name="price-monitor",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def watch_tokens(self, chain, tokens, chat_id):
        """Add command result tokens to the live price tracker."""
        if not getattr(config, "PRICE_TRACK_ENABLED", True):
            return 0

        now = time.time()
        watched = 0
        tokens_to_watch = tokens[: self.max_tokens]

        with self.lock:
            for token in tokens_to_watch:
                key = self._track_key(chat_id, chain, token)
                price = self._to_float(token.get("price_usd"))
                if not key or price is None or price <= 0:
                    continue

                existing = self.tracked.get(key, {})
                self.tracked[key] = {
                    "chat_id": chat_id,
                    "chain": chain,
                    "address": token.get("contract_address", "N/A"),
                    "name": token.get("name", "N/A"),
                    "symbol": token.get("symbol", "N/A"),
                    "price": price,
                    "notified_price": price,
                    "last_notified_at": existing.get("last_notified_at", 0),
                    "last_seen_at": now,
                }
                watched += 1

        logger.info("Price tracker watching %s token(s) for %s.", watched, chain.upper())
        return watched

    def run(self):
        logger.info(
            "Price monitor started: interval=%ss min_change=%s%% cooldown=%ss",
            self.interval,
            self.min_change_percent,
            self.cooldown,
        )

        while not self.stop_event.is_set():
            self.check_once()
            if self.stop_event.wait(self.interval):
                break

    def check_once(self):
        with self.lock:
            chains = sorted({item["chain"] for item in self.tracked.values()})

        for chain in chains:
            try:
                result = self.scraper_service.fetch_and_save(chain)
                if not result.get("success"):
                    logger.warning(
                        "Price monitor fetch failed for %s: %s",
                        chain,
                        result.get("error"),
                    )
                    continue

                latest_by_address = self._index_tokens(chain, result.get("tokens", []))
                self._process_chain_prices(chain, latest_by_address)
            except Exception as exc:
                logger.error("Price monitor error for %s: %s", chain, exc)

    def _process_chain_prices(self, chain, latest_by_address):
        now = time.time()
        updates = []

        with self.lock:
            tracked_items = [
                (key, dict(item))
                for key, item in self.tracked.items()
                if item["chain"] == chain
            ]

        for key, item in tracked_items:
            latest = latest_by_address.get(self._normalize_address(chain, item["address"]))
            if not latest:
                continue

            current_price = self._to_float(latest.get("price_usd"))
            if current_price is None or current_price <= 0:
                continue

            notified_price = item.get("notified_price") or item.get("price")
            if not notified_price:
                continue

            change_percent = ((current_price - notified_price) / notified_price) * 100
            should_notify = abs(change_percent) >= self.min_change_percent
            cooldown_done = now - item.get("last_notified_at", 0) >= self.cooldown

            with self.lock:
                if key in self.tracked:
                    self.tracked[key]["price"] = current_price
                    self.tracked[key]["last_seen_at"] = now

            if should_notify and cooldown_done:
                updates.append((key, item, latest, notified_price, current_price, change_percent))

        for key, item, latest, old_price, new_price, change_percent in updates:
            message = self.format_price_update_message(
                chain=chain,
                item=item,
                latest=latest,
                old_price=old_price,
                new_price=new_price,
                change_percent=change_percent,
            )
            self.send_message(message, chat_id=item["chat_id"])

            with self.lock:
                if key in self.tracked:
                    self.tracked[key]["notified_price"] = new_price
                    self.tracked[key]["last_notified_at"] = now

    def format_price_update_message(self, chain, item, latest, old_price, new_price, change_percent):
        name = latest.get("name") or item.get("name", "N/A")
        symbol = latest.get("symbol") or item.get("symbol", "N/A")
        contract = latest.get("contract_address") or item.get("address", "N/A")
        mcap = self.scraper_service._format_number(latest.get("market_cap", 0))
        liquidity = self.scraper_service._format_number(latest.get("liquidity", 0))
        volume = self.scraper_service._format_number(latest.get("volume_24h", 0))
        change_5m = self._format_percent(latest.get("price_change_5m", 0))
        change_1h = self._format_percent(latest.get("price_change_1h", 0))
        direction = "artti" if change_percent > 0 else "dustu"

        return (
            f"Fiyat guncellendi ({chain.upper()})\n"
            f"{name} (${symbol})\n"
            f"Eski: {self._format_price(old_price)}\n"
            f"Yeni: {self._format_price(new_price)}\n"
            f"Degisim: {self._format_percent(change_percent)} ({direction})\n"
            f"MCap: {mcap} | Liq: {liquidity} | Vol: {volume}\n"
            f"5m: {change_5m} | 1h: {change_1h}\n"
            f"CA: {contract}"
        )

    def _index_tokens(self, chain, tokens):
        indexed = {}
        for token in tokens:
            address = self._normalize_address(chain, token.get("contract_address"))
            if address:
                indexed[address] = token
        return indexed

    def _track_key(self, chat_id, chain, token):
        address = self._normalize_address(chain, token.get("contract_address"))
        if not address:
            return None
        return f"{chat_id}:{chain}:{address}"

    def _normalize_address(self, chain, address):
        address = str(address or "").strip()
        if not address or address == "N/A":
            return None
        if chain == "eth":
            return address.lower()
        return address

    def _to_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_price(self, price):
        price = self._to_float(price)
        if price is None or price <= 0:
            return "N/A"
        if price < 0.0001:
            return f"${price:.10f}"
        if price < 1:
            return f"${price:.6f}"
        return f"${price:,.2f}"

    def _format_percent(self, value):
        value = self._to_float(value)
        if value is None:
            return "N/A"
        prefix = "+" if value > 0 else ""
        return f"{prefix}{value:.2f}%"
