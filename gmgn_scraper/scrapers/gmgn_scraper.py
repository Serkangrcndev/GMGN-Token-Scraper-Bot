"""
GMGN.ai Token Scraper
Birden fazla chain destekler. En son çıkan token ilk sırada gelir.
Selenium/Chromium gerektirmez - doğrudan API kullanır.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from datetime import datetime

import config

logger = logging.getLogger(__name__)


class GmgnScraper:
    def __init__(self):
        self.base_url = config.GMGN_BASE_URL
        self.session = self._create_session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://gmgn.ai/",
            "Origin": "https://gmgn.ai",
        }

    def _create_session(self):
        """Retry mekanizmalı session oluştur"""
        session = requests.Session()
        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def fetch_trending_tokens(self, chain, time_period=None, order_by=None):
        """
        Belirtilen chain için GMGN.ai'den token verilerini çeker.
        Varsayılan sıralama: open_timestamp (en yeni ilk sırada)
        """
        time_period = time_period or config.GMGN_TIME_PERIOD
        order_by = order_by or config.GMGN_ORDER_BY

        url = f"{self.base_url}/{chain}/swaps/{time_period}"
        params = {
            "orderby": order_by,
            "direction": config.GMGN_DIRECTION,
        }
        for f in config.GMGN_FILTERS:
            params.setdefault("filters[]", [])
            if isinstance(params["filters[]"], list):
                params["filters[]"].append(f)

        logger.info(f"GMGN API -> chain={chain}, period={time_period}, orderby={order_by}")

        try:
            response = self.session.get(
                url,
                params=params,
                headers=self.headers,
                timeout=config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                tokens = data.get("data", {}).get("rank", [])
                # En son çıkan token ilk sırada olacak şekilde sırala
                tokens = sorted(
                    tokens,
                    key=lambda t: t.get("open_timestamp", 0),
                    reverse=True,
                )
                logger.info(f"Basariyla {len(tokens)} token cekildi ({chain.upper()}).")
                return tokens
            else:
                logger.error(f"API hata: {data.get('code')} - {data.get('msg', '')}")
                return []

        except requests.exceptions.Timeout:
            logger.error("API zaman asimi.")
            return []
        except requests.exceptions.ConnectionError:
            logger.error("API baglanti hatasi.")
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Hatasi: {e}")
            return []
        except Exception as e:
            logger.error(f"Beklenmeyen hata: {str(e)}")
            return []

    def parse_token_data(self, raw_tokens, chain):
        """Ham token verilerini temiz formata dönüştürür."""
        parsed_tokens = []

        for token in raw_tokens:
            try:
                # open_timestamp'i okunabilir tarihe çevir
                open_ts = token.get("open_timestamp", 0)
                if open_ts:
                    created_at = datetime.fromtimestamp(open_ts).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created_at = "N/A"

                parsed = {
                    "name": token.get("name", "N/A"),
                    "symbol": token.get("symbol", "N/A"),
                    "contract_address": token.get("address", "N/A"),
                    "price_usd": token.get("price", 0),
                    "market_cap": token.get("market_cap", 0),
                    "liquidity": token.get("liquidity", 0),
                    "volume_24h": token.get("volume", 0),
                    "swaps": token.get("swaps", 0),
                    "buys": token.get("buys", 0),
                    "sells": token.get("sells", 0),
                    "holders": token.get("holder_count", 0),
                    "price_change_1h": token.get("price_change_percent1h", 0),
                    "price_change_5m": token.get("price_change_percent5m", 0),
                    "buy_tax": token.get("buy_tax", 0),
                    "sell_tax": token.get("sell_tax", 0),
                    "is_honeypot": token.get("is_honeypot", False),
                    "renounced": token.get("renounced", False),
                    "open_timestamp": open_ts,
                    "created_at": created_at,
                    "smart_money_buys": token.get("smart_degen", 0),
                    "logo": token.get("logo", ""),
                    "chain": chain,
                    "fetched_at": datetime.now().isoformat(),
                }
                parsed_tokens.append(parsed)
            except Exception as e:
                logger.warning(f"Token parse hatasi: {str(e)}")
                continue

        return parsed_tokens

    def scrape(self, chain, time_period=None, order_by=None):
        """
        Belirtilen chain için veriyi çeker ve parse eder.
        """
        # Chain'in config'de tanımlı olup olmadığını kontrol et
        if chain not in config.CHAINS:
            logger.error(f"Desteklenmeyen chain: {chain}")
            return []

        raw_tokens = self.fetch_trending_tokens(chain, time_period, order_by)
        if not raw_tokens:
            return []
        return self.parse_token_data(raw_tokens, chain)
