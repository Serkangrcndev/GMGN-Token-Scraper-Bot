"""
Scraper Service - Scraper işlemlerini yöneten servis katmanı.
Veri çekme, JSON kaydetme ve formatlama işlemleri.
"""

import json
import os
import logging
from datetime import datetime

from scrapers.gmgn_scraper import GmgnScraper
import config

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self):
        self.scraper = GmgnScraper()
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Data klasörünün var olduğundan emin ol"""
        os.makedirs(config.DATA_DIR, exist_ok=True)

    def get_available_chains(self):
        """Config'de tanımlı chain listesini döndür"""
        return list(config.CHAINS.keys())

    def fetch_and_save(self, chain, time_period=None, order_by=None):
        """
        Belirtilen chain için token verilerini çek ve JSON'a kaydet.
        """
        import time
        start_time = time.time()

        try:
            tokens = self.scraper.scrape(chain, time_period, order_by)

            if not tokens:
                return {
                    "success": False,
                    "error": "Veri cekilemedi veya sonuc bos.",
                    "token_count": 0,
                }

            # JSON'a kaydet (her chain için ayrı dosya)
            json_path = f"data/gmgn_{chain}_tokens.json"
            output_data = {
                "chain": chain,
                "url": config.CHAINS.get(chain, ""),
                "time_period": time_period or config.GMGN_TIME_PERIOD,
                "order_by": order_by or config.GMGN_ORDER_BY,
                "fetched_at": datetime.now().isoformat(),
                "token_count": len(tokens),
                "tokens": tokens,
            }

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            duration = round(time.time() - start_time, 2)
            logger.info(f"{len(tokens)} token kaydedildi -> {json_path} ({duration}s)")

            return {
                "success": True,
                "token_count": len(tokens),
                "tokens": tokens,
                "json_path": json_path,
                "duration": duration,
                "chain": chain,
            }

        except Exception as e:
            logger.error(f"Scraper service hatasi: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "token_count": 0,
            }

    def format_token_message(self, tokens, chain, max_count=None):
        """Token verilerini Telegram mesajı formatına dönüştürür."""
        max_count = max_count or config.MAX_TOKENS_TO_SHOW
        tokens_to_show = tokens[:max_count]

        lines = []
        lines.append("============================")
        lines.append(f"  GMGN.ai - {chain.upper()} Trending Tokens")
        lines.append(f"  Siralama: En Yeni Token Ilk Sirada")
        lines.append(f"  Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("============================\n")

        for i, token in enumerate(tokens_to_show, 1):
            name = token.get("name", "N/A")
            symbol = token.get("symbol", "N/A")
            price = token.get("price_usd", 0)
            mcap = token.get("market_cap", 0)
            liq = token.get("liquidity", 0)
            swaps = token.get("swaps", 0)
            change_1h = token.get("price_change_1h", 0)
            buys = token.get("buys", 0)
            sells = token.get("sells", 0)
            holders = token.get("holders", 0)
            contract = token.get("contract_address", "N/A")
            created_at = token.get("created_at", "N/A")

            # Fiyat formatlama
            if price and price > 0:
                if price < 0.0001:
                    price_str = f"${price:.10f}"
                elif price < 1:
                    price_str = f"${price:.6f}"
                else:
                    price_str = f"${price:,.2f}"
            else:
                price_str = "N/A"

            mcap_str = self._format_number(mcap)
            liq_str = self._format_number(liq)

            change_icon = "+" if change_1h and change_1h > 0 else ""

            lines.append(f"#{i} {name} (${symbol})")
            lines.append(f"   Olusturulma: {created_at}")
            lines.append(f"   Fiyat: {price_str}")
            lines.append(f"   MCap: {mcap_str} | Liq: {liq_str}")
            lines.append(f"   1h: {change_icon}{change_1h:.2f}%" if change_1h else "   1h: N/A")
            lines.append(f"   Swaps: {swaps} | B: {buys} | S: {sells}")
            lines.append(f"   Holders: {holders}")
            lines.append(f"   CA: {contract[:20]}...{contract[-6:]}" if len(str(contract)) > 26 else f"   CA: {contract}")
            lines.append("")

        lines.append(f"Toplam {len(tokens)} token bulundu.")
        if len(tokens) > max_count:
            lines.append(f"(Ilk {max_count} tanesi gosteriliyor)")

        return "\n".join(lines)

    def _format_number(self, num):
        """Büyük sayıları okunabilir formata dönüştür"""
        if not num or num == 0:
            return "N/A"
        try:
            num = float(num)
            if num >= 1_000_000_000:
                return f"${num / 1_000_000_000:.2f}B"
            elif num >= 1_000_000:
                return f"${num / 1_000_000:.2f}M"
            elif num >= 1_000:
                return f"${num / 1_000:.2f}K"
            else:
                return f"${num:.2f}"
        except:
            return "N/A"
