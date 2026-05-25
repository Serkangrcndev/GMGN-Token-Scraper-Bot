"""
Background monitor for new GMGN tokens.

The monitor keeps a persistent set of seen contract addresses per chain. On
startup it seeds the state from the current GMGN response, so the bot does not
spam old tokens when it is first enabled.
"""

import json
import logging
import os
import threading
from datetime import datetime

import config
from services.scraper_service import ScraperService

logger = logging.getLogger(__name__)


class NewTokenMonitor:
    def __init__(self, send_message):
        self.send_message = send_message
        self.scraper_service = ScraperService()
        self.chains = [
            chain
            for chain in getattr(config, "AUTO_NOTIFY_CHAINS", ["eth"])
            if chain in config.CHAINS
        ]
        self.interval = max(5, int(getattr(config, "AUTO_NOTIFY_INTERVAL_SECONDS", 30)))
        self.max_tokens = max(1, int(getattr(config, "AUTO_NOTIFY_MAX_TOKENS_PER_CYCLE", 10)))
        self.keep_limit = max(100, int(getattr(config, "AUTO_NOTIFY_STATE_KEEP_LIMIT", 5000)))
        self.state_file = getattr(config, "AUTO_NOTIFY_STATE_FILE", "data/notified_tokens.json")
        self.stop_event = threading.Event()
        self.thread = None
        self.state_lock = threading.Lock()
        self.state = self._load_state()

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if not self.chains:
            logger.warning("Auto notify monitor has no valid chains.")
            return

        self.thread = threading.Thread(
            target=self.run,
            name="new-token-monitor",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def run(self):
        logger.info(
            "Auto notify monitor started: chains=%s interval=%ss",
            ",".join(self.chains),
            self.interval,
        )
        self._bootstrap_state()

        while not self.stop_event.is_set():
            self.check_once()
            if self.stop_event.wait(self.interval):
                break

    def check_once(self):
        for chain in self.chains:
            try:
                result = self.scraper_service.fetch_and_save(chain)
                if not result.get("success"):
                    logger.warning(
                        "Auto notify fetch failed for %s: %s",
                        chain,
                        result.get("error"),
                    )
                    continue

                tokens = result.get("tokens", [])
                new_tokens = self._find_new_tokens(chain, tokens)
                notified_tokens = None
                if new_tokens:
                    notified_tokens = self._notify_new_tokens(chain, new_tokens)
                self._remember_tokens(chain, tokens, notified_tokens)
            except Exception as exc:
                logger.error("Auto notify error for %s: %s", chain, exc)

    def _bootstrap_state(self):
        changed = False
        with self.state_lock:
            chains_state = self.state.setdefault("chains", {})

        for chain in self.chains:
            with self.state_lock:
                already_seeded = bool(chains_state.get(chain))
            if already_seeded:
                continue

            result = self.scraper_service.fetch_and_save(chain)
            if not result.get("success"):
                logger.warning(
                    "Auto notify bootstrap failed for %s: %s",
                    chain,
                    result.get("error"),
                )
                continue

            tokens = result.get("tokens", [])
            keys = self._token_keys(chain, tokens)
            with self.state_lock:
                chains_state[chain] = keys[: self.keep_limit]
            changed = True
            logger.info("Auto notify seeded %s with %s tokens.", chain, len(keys))

        if changed:
            self._save_state()

    def _find_new_tokens(self, chain, tokens):
        with self.state_lock:
            seen = set(self.state.setdefault("chains", {}).get(chain, []))

        new_tokens = []
        for token in tokens:
            key = self._token_key(chain, token)
            if key and key not in seen:
                new_tokens.append(token)

        return self._sort_tokens(new_tokens)

    def _remember_tokens(self, chain, tokens, notified_tokens=None):
        tokens_to_remember = notified_tokens if notified_tokens is not None else tokens
        current_keys = self._token_keys(chain, tokens_to_remember)
        if not current_keys:
            return

        with self.state_lock:
            chains_state = self.state.setdefault("chains", {})
            existing = chains_state.get(chain, [])
            combined = []
            used = set()
            for key in current_keys + existing:
                if key and key not in used:
                    combined.append(key)
                    used.add(key)
                if len(combined) >= self.keep_limit:
                    break
            chains_state[chain] = combined

        self._save_state()

    def _notify_new_tokens(self, chain, tokens):
        total = len(tokens)
        logger.info("Auto notify found %s new token(s) on %s.", total, chain.upper())

        tokens_to_send = tokens[: self.max_tokens]
        for token in tokens_to_send:
            message = self.format_new_token_message(token, chain)
            self.send_message(message)

        remaining = total - len(tokens_to_send)
        if remaining > 0:
            self.send_message(
                f"{chain.upper()} icin {remaining} yeni token daha var. "
                "Sonraki kontrolde gondermeye devam edecegim."
            )

        return tokens_to_send

    def format_new_token_message(self, token, chain):
        name = token.get("name", "N/A")
        symbol = token.get("symbol", "N/A")
        contract = token.get("contract_address", "N/A")
        created_at = token.get("created_at", "N/A")
        price = self._format_price(token.get("price_usd", 0))
        mcap = self.scraper_service._format_number(token.get("market_cap", 0))
        liquidity = self.scraper_service._format_number(token.get("liquidity", 0))
        volume = self.scraper_service._format_number(token.get("volume_24h", 0))
        change_5m = self._format_percent(token.get("price_change_5m", 0))
        change_1h = self._format_percent(token.get("price_change_1h", 0))
        swaps = token.get("swaps", 0)
        buys = token.get("buys", 0)
        sells = token.get("sells", 0)
        holders = token.get("holders", 0)
        honeypot = self._format_bool(token.get("is_honeypot"))
        renounced = self._format_bool(token.get("renounced"))
        trade_url = self._trade_url(chain, contract)

        return (
            f"Yeni token bulundu ({chain.upper()})\n"
            f"{name} (${symbol})\n"
            f"Olusturulma: {created_at}\n"
            f"Fiyat: {price}\n"
            f"MCap: {mcap} | Liq: {liquidity} | Vol: {volume}\n"
            f"5m: {change_5m} | 1h: {change_1h}\n"
            f"Swaps: {swaps} | B: {buys} | S: {sells}\n"
            f"Holders: {holders}\n"
            f"Honeypot: {honeypot} | Renounced: {renounced}\n"
            f"CA: {contract}\n"
            f"Islem yapmak icin tiklayin: {trade_url}"
        )

    def _load_state(self):
        if not os.path.exists(self.state_file):
            return {"version": 1, "chains": {}, "updated_at": None}

        try:
            with open(self.state_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            logger.warning("Could not load auto notify state: %s", exc)
            return {"version": 1, "chains": {}, "updated_at": None}

        if not isinstance(data, dict):
            return {"version": 1, "chains": {}, "updated_at": None}

        data.setdefault("version", 1)
        data.setdefault("chains", {})
        return data

    def _save_state(self):
        with self.state_lock:
            data = dict(self.state)
            data["updated_at"] = datetime.now().isoformat()

        os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
        tmp_file = f"{self.state_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_file, self.state_file)

        with self.state_lock:
            self.state["updated_at"] = data["updated_at"]

    def _token_keys(self, chain, tokens):
        keys = []
        seen = set()
        for token in tokens:
            key = self._token_key(chain, token)
            if key and key not in seen:
                keys.append(key)
                seen.add(key)
        return keys

    def _token_key(self, chain, token):
        address = str(token.get("contract_address") or "").strip()
        if not address or address == "N/A":
            return None
        if chain == "eth":
            address = address.lower()
        return f"{chain}:{address}"

    def _trade_url(self, chain, contract):
        contract = str(contract or "").strip()
        if not contract or contract == "N/A":
            return "N/A"
        return f"https://gmgn.ai/{chain}/token/{contract}"

    def _sort_tokens(self, tokens):
        return sorted(
            tokens,
            key=lambda token: token.get("open_timestamp") or 0,
            reverse=True,
        )

    def _format_price(self, price):
        try:
            price = float(price)
        except (TypeError, ValueError):
            return "N/A"

        if price <= 0:
            return "N/A"
        if price < 0.0001:
            return f"${price:.10f}"
        if price < 1:
            return f"${price:.6f}"
        return f"${price:,.2f}"

    def _format_percent(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "N/A"

        prefix = "+" if value > 0 else ""
        return f"{prefix}{value:.2f}%"

    def _format_bool(self, value):
        if value is True or value == 1 or value == "1":
            return "Evet"
        if value is False or value == 0 or value == "0":
            return "Hayir"
        return "N/A"
