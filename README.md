# 🚀 GMGN Token Scraper Bot

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Ethereum](https://img.shields.io/badge/Ethereum-ETH-627EEA?style=for-the-badge&logo=ethereum&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**GMGN.ai üzerinden yeni Ethereum tokenlarını gerçek zamanlı takip eden, Telegram üzerinden bildirim gönderen tam otomatik kripto token scraper botu.**

[Kurulum](#kurulum) • [Yapılandırma](#yapılandırma) • [Kullanım](#kullanım) • [Özellikler](#özellikler)

</div>

---

## ✨ Özellikler

| Özellik | Açıklama |
|---|---|
| 🔍 **Akıllı Scraping** | Selenium/Chromium gerektirmez — GMGN.ai API'sini doğrudan kullanır |
| 📢 **Otomatik Bildirim** | Her 30 saniyede bir yeni ETH tokenlarını Telegram grubuna gönderir |
| 💹 **Canlı Fiyat Takibi** | Listelenen tokenların fiyat değişimlerini %1 hassasiyetle izler |
| 🛡️ **Honeypot Filtresi** | Yalnızca `verified`, `renounced`, `not_honeypot` tokenları listeler |
| ⚡ **Çoklu İş Parçacığı** | 4 paralel komut işçisi ile eşzamanlı komutları yönetir |
| 🔒 **Tek Kopya Kilidi** | Aynı anda iki bot açılmasını engelleyen socket kilidi |
| 📄 **JSON Çıktısı** | Token verilerini `data/gmgn_tokens.json` dosyasına kaydeder |
| 🔁 **Otomatik Yeniden Deneme** | Ağ hatalarında exponential backoff ile yeniden dener |

---

## 🏗️ Mimari

```
GMGN.ai API
    │
    ▼
GmgnScraper (scrapers/)
    │  Ham token verisi çeker ve parse eder
    ▼
ScraperService (services/)
    │  İş mantığı, formatlama, JSON kaydetme
    ├──► NewTokenMonitor   →  Yeni token bildirimleri (her 30s)
    └──► PriceMonitor      →  Fiyat değişim uyarıları (her 20s)
    │
    ▼
TelegramBot (bot/)
    │  Long-polling ile komutları dinler
    └──► Telegram Grubu
```

---

## 📦 Gereksinimler

- Python **3.8+**
- `requests >= 2.28.0`
- `urllib3 >= 1.26.0`
- Bir **Telegram Bot Token** ([BotFather](https://t.me/BotFather)'dan alın)
- Bir **Telegram Grup/Chat ID**

---

## 🚀 Kullanım

### Windows — Tek Tıkla Başlat

```
start_eth_bot.bat dosyasına çift tıklayın
```

> ⚠️ Bot zaten çalışıyorsa yeni kopya açılmaz ve uyarı verilir.

### Manuel Başlatma

```bash
cd gmgn_scraper
python main.py
```

---

## 💬 Telegram Bot Komutları

| Komut | Açıklama |
|---|---|
| `/start` | Botu başlat, mevcut komutları listele |
| `/help` | Yardım mesajı |
| `/eth` | En yeni Ethereum tokenlarını çek ve listele |

> **Not:** `/eth` komutu çalıştırıldıktan sonra dönen tokenlar otomatik olarak fiyat takibine alınır.

---

## 📊 Çıktı Formatı

Her yeni token için aşağıdaki bilgiler Telegram'a gönderilir:

```
Yeni token bulundu (ETH)
PepeRocket ($ROCKET)
Oluşturulma: 2024-01-15 14:32:01
Fiyat: $0.000042
MCap: $420K | Liq: $85K | Vol: $1.2M
5m: +12.50% | 1h: +38.20%
Swaps: 1240 | B: 980 | S: 260
Holders: 512
Honeypot: Hayır | Renounced: Evet
CA: 0xAbCd...1234
İşlem yapmak için tıklayın: https://gmgn.ai/eth/token/0xAbCd...1234
```

---

## 📁 Proje Yapısı

```
gmgn-token-scraper/
├── 📄 README.md
├── 🪟 start_eth_bot.bat          # Windows için tek tıkla başlatma
└── 📂 gmgn_scraper/
    ├── 📄 main.py                # Ana giriş noktası
    ├── ⚙️ config.py              # Tüm ayarlar buraya
    ├── 📄 requirements.txt       # Python bağımlılıkları
    ├── 📂 bot/
    │   └── telegram_bot.py       # Telegram long-polling botu
    ├── 📂 scrapers/
    │   └── gmgn_scraper.py       # GMGN.ai API istemcisi
    ├── 📂 services/
    │   ├── scraper_service.py    # İş mantığı katmanı
    │   ├── token_monitor.py      # Yeni token arka plan izleyici
    │   └── price_monitor.py      # Fiyat değişim izleyici
    └── 📂 data/
        ├── gmgn_tokens.json      # Son çekilen tokenlar
        └── notified_tokens.json  # Bildirim gönderilen token geçmişi
```

---

## ⚠️ Yasal Uyarı

Bu proje yalnızca **eğitim ve araştırma** amaçlıdır. Kripto para yatırımları yüksek risk içerir. Bu botun sağladığı veriler yatırım tavsiyesi değildir. Kullanımdan doğacak her türlü kayıptan kullanıcı sorumludur.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) altında dağıtılmaktadır.

---

<div align="center">
  <sub>⭐ Projeyi beğendiyseniz yıldız vermeyi unutmayın!</sub>
</div>
