import time
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import TelegramError
import logging

# ---------------------- НАЛАШТУВАННЯ ----------------------
TELEGRAM_TOKEN = "ТВОЙ_ТОКЕН_ТУТ"
CHAT_ID = "ТВОЙ_CHAT_ID"
CHECK_INTERVAL = 180  # 3 хвилини
PERCENT_THRESHOLD = 70  # Відсоток ставок для сигналу

# ---------------------- ЛОГІНГ ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ---------------------- СПИСОК САЙТІВ ----------------------
SITES = [
    {"name": "Inforadar", "url": "https://inforadar.live/", "signal_class": "signal"},
    {"name": "Betwatch", "url": "https://betwatch.fr/", "signal_class": "signal"},
    {"name": "SkyBet", "url": "https://www.skybet.com/football", "signal_class": "signal"},
    {"name": "Unibet", "url": "https://www.unibet.com/betting/football", "signal_class": "signal"},
    {"name": "1xBet", "url": "https://1xbet.com/football", "signal_class": "signal"},
    {"name": "MafiaBet", "url": "https://mafia.bet/football", "signal_class": "signal"},
    {"name": "OddsPortal", "url": "https://www.oddsportal.com/matches/", "signal_class": "signal"},
    {"name": "Betfair", "url": "https://www.betfair.com/exchange/football", "signal_class": "signal"},
    {"name": "Pinnacle", "url": "https://www.pinnacle.com/en/football", "signal_class": "signal"},
    {"name": "WilliamHill", "url": "https://www.williamhill.com/football", "signal_class": "signal"},
]

# ---------------------- ПАРСЕР ----------------------
def parse_site(site):
    signals = []
    try:
        r = requests.get(site["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for s in soup.find_all("div", class_=site["signal_class"]):
            match_tag = s.find("span", class_="match")
            prediction_tag = s.find("span", class_="prediction")
            confidence_tag = s.find("span", class_="confidence")
            if not match_tag or not prediction_tag or not confidence_tag:
                continue
            match = match_tag.text.strip()
            market = prediction_tag.text.strip()
            percent_text = confidence_tag.text.strip().replace("%","")
            percent = int(percent_text) if percent_text.isdigit() else 0
            if percent >= PERCENT_THRESHOLD:
                signals.append({
                    "site": site["name"],
                    "match": match,
                    "market": market,
                    "percent": percent,
                    "link": site["url"]
                })
    except Exception as e:
        logging.warning(f"[{site['name']}] parse error: {e}")
    return signals

# ---------------------- ВІДПРАВКА СИГНАЛУ ----------------------
def send_signal(bot, signal):
    message = (
        f"📢 <b>СИГНАЛ</b>\n"
        f"📌 <b>Сайт:</b> {signal['site']}\n"
        f"⚽️ <b>Матч:</b> {signal['match']}\n"
        f"🎯 <b>Ринок:</b> {signal['market']}\n"
        f"📊 <b>% ставок:</b> {signal['percent']}%\n"
        f"🔗 <a href='{signal['link']}'>Перейти</a>"
    )
    try:
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML", disable_web_page_preview=True)
        logging.info(f"Сигнал відправлений: {signal['match']} [{signal['site']}]")
    except TelegramError as e:
        logging.error(f"Помилка Telegram: {e}")

# ---------------------- ОСНОВНИЙ ЦИКЛ ----------------------
def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logging.info("Бот запущений і працює 24/7!")
    sent_signals = set()  # для уникнення дублювання
    while True:
        all_signals = []
        for site in SITES:
            all_signals += parse_site(site)
        for s in all_signals:
            identifier = f"{s['site']}|{s['match']}|{s['market']}"
            if identifier not in sent_signals:
                send_signal(bot, s)
                sent_signals.add(identifier)
        if not all_signals:
            logging.info("Сигналів немає на цей момент.")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
