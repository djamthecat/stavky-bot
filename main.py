import os
import time
import logging
import telebot
from flask import Flask, request
from threading import Thread
from bs4 import BeautifulSoup
import requests

# --- Selenium / Betfair ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ========= Конфіг =========
TOKEN = os.environ['TOKEN']                       # Telegram Bot Token
RENDER_URL = os.environ['RENDER_URL']             # https://<service>.onrender.com
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')   # не обов'язково
DEMO_MODE = os.environ.get('DEMO_MODE', '0') == '1'    # якщо 1 — відправляємо тестові сигнали
SAMPLE_DIR = os.environ.get('SAMPLE_DIR', '')          # шлях до папки з .html для файлового парсингу (необов.)
CHECK_INTERVAL_SEC = int(os.environ.get('CHECK_INTERVAL_SEC', '120'))

# ========= Ініт =========
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
bot = telebot.TeleBot(TOKEN)
USERS = []                # підписники в поточній сесії
sent_signals = set()      # щоб не дублювати відправлене
prev_signals_data = {}    # для порівняння змін (confidence/odds)
app = Flask(__name__)

# --- Глобальний Selenium драйвер (переюз) ---
driver = None
def ensure_driver():
    """Створюємо 1 headless Chrome і переюзаємо (менше банів/пам’яті)."""
    global driver
    if driver is not None:
        return driver
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1280,1600")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118 Safari/537.36")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    driver.set_page_load_timeout(40)
    return driver

# ========= Flask routes =========
@app.route('/')
def index():
    return "Football Signals Bot is running!"

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('UTF-8'))
    bot.process_new_updates([update])
    return "ok", 200

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    s = bot.set_webhook(f"{RENDER_URL}/{TOKEN}")
    return "Webhook set!" if s else "Webhook failed!"

# Опц. ручне тест-повідомлення: /send_test?key=<будь-що>
@app.route('/send_test')
def send_test():
    for uid in USERS or ([int(ADMIN_CHAT_ID)] if ADMIN_CHAT_ID else []):
        try:
            bot.send_message(uid, "✅ Тест: бот онлайн і вміє надсилати повідомлення.")
        except Exception as e:
            logging.error(f"Test send error to {uid}: {e}")
    return "sent"

# ========= Telegram handlers =========
@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id not in USERS:
        USERS.append(message.chat.id)
    bot.send_message(message.chat.id,
                     "Привіт! Ти отримуватимеш футбольні сигнали (1X2, тотали, фори). "
                     "Команди: /stop — відписатися.")
    logging.info(f"USERS: {USERS}")
    if DEMO_MODE:
        bot.send_message(message.chat.id, "🧪 DEMO_MODE увімкнено — отримуватимеш тестові сигнали.")

@bot.message_handler(commands=['stop'])
def stop(message):
    if message.chat.id in USERS:
        USERS.remove(message.chat.id)
    bot.send_message(message.chat.id, "Сигнали більше не надсилатимуться.")
    logging.info(f"USERS: {USERS}")

# ========= Допоміжне =========
def get_bet_type(prediction: str) -> str:
    pred = prediction.lower()
    if any(x in pred for x in ["over", "under", "тотал"]):
        return "Тотал"
    if "handicap" in pred or "фора" in pred or "+" in pred or "-" in pred:
        return "Фора"
    if any(x in pred for x in [" 1 ", " x ", " 2 ", "home", "draw", "away"]):
        return "Результат"
    return "Інше"

def safe_float(s, default=0.0):
    try:
        return float(str(s).strip().replace(",", "."))
    except Exception:
        return default

# ========= HTML-парсинг сайтів (приклади шаблонів) =========
sites = [
    # Для кожного сайту треба підібрати реальні селектори класів/тегів
    {"name": "Inforadar", "url": "https://inforadar.live/", "container": ("div", {"class": "signal"})},
    {"name": "Betwatch", "url": "https://betwatch.fr/", "container": ("div", {"class": "signal"})},
]

def parse_html_site(site, prev_data):
    """Генерик парсер за шаблоном: підлаштуй селектори під реальний HTML."""
    signals = []
    try:
        logging.info(f"[HTML] Fetch {site['name']} {site['url']}")
        r = requests.get(site['url'], timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        tag, attrs = site['container']
        for block in soup.find_all(tag, attrs=attrs):
            match_tag = block.find('span', class_='match') or block.find('div', class_='match')
            pred_tag = block.find('span', class_='prediction') or block.find('div', class_='prediction')
            conf_tag = block.find('span', class_='confidence')
            odds_tag = block.find('span', class_='odds')

            if not (match_tag and pred_tag):
                continue

            match = match_tag.get_text(strip=True)
            prediction = pred_tag.get_text(strip=True)
            bet_type = get_bet_type(prediction)
            confidence = 0
            if conf_tag:
                confidence = int(str(conf_tag.get_text(strip=True)).replace('%', '').strip() or 0)
            odds = safe_float(odds_tag.get_text(strip=True) if odds_tag else 0, 0.0)

            identifier = f"{site['name']}|{match}|{prediction}"
            changed = (
                identifier not in prev_data
                or abs(prev_data[identifier]['confidence'] - confidence) >= 5
                or abs(prev_data[identifier]['odds'] - odds) >= 0.05
            )
            if changed:
                signals.append({
                    "site": site['name'],
                    "match": match,
                    "prediction": prediction,
                    "bet_type": bet_type,
                    "confidence": confidence,
                    "odds": odds
                })
                prev_data[identifier] = {"confidence": confidence, "odds": odds}
    except Exception as e:
        logging.warning(f"[HTML] {site['name']} parse error: {e}")
    return signals

# ========= Файловий парсер (для тесту на збережених HTML) =========
def parse_html_file(file_path, site_name="FILE"):
    signals = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        for block in soup.find_all('div', class_='signal'):
            match_tag = block.find('span', class_='match')
            pred_tag = block.find('span', class_='prediction')
            conf_tag = block.find('span', class_='confidence')
            odds_tag = block.find('span', class_='odds')
            if not (match_tag and pred_tag):
                continue
            match = match_tag.get_text(strip=True)
            prediction = pred_tag.get_text(strip=True)
            bet_type = get_bet_type(prediction)
            confidence = int(str(conf_tag.get_text(strip=True)).replace('%', '').strip() or 0) if conf_tag else 0
            odds = safe_float(odds_tag.get_text(strip=True) if odds_tag else 0, 0.0)
            signals.append({
                "site": site_name,
                "match": match,
                "prediction": prediction,
                "bet_type": bet_type,
                "confidence": confidence,
                "odds": odds
            })
    except Exception as e:
        logging.warning(f"[FILE] {file_path} parse error: {e}")
    return signals

# ========= Betfair (Selenium) =========
def parse_betfair_market_cards(drv):
    markets = []
    tried_urls = [
        "https://www.betfair.com/exchange/football",
        "https://www.betfair.com/exchange/plus/football"
    ]
    loaded = False
    for url in tried_urls:
        try:
            drv.get(url)
            WebDriverWait(drv, 20).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'/exchange/football/event/')] | //a[contains(@href,'/exchange/plus/football/market/')]"))
            )
            loaded = True
            break
        except Exception:
            continue
    if not loaded:
        return markets

    time.sleep(2)
    event_links = drv.find_elements(By.XPATH, "//a[contains(@href,'/exchange/football/event/')]")
    if not event_links:
        market_links = drv.find_elements(By.XPATH, "//a[contains(@href,'/exchange/plus/football/market/')]")
        for ml in market_links[:20]:
            try:
                href = ml.get_attribute("href")
                comp_title = ml.text.strip()
                markets.append({"event": comp_title or "Football", "market_url": href})
            except Exception:
                pass
        return markets

    for el in event_links[:20]:
        try:
            href = el.get_attribute("href")
            title = el.text.strip()
            if href:
                markets.append({"event": title or "Football", "event_url": href})
        except Exception:
            continue
    return markets

def open_event_and_collect_markets(drv, event):
    signals = []
    url = event.get("event_url") or event.get("market_url")
    if not url:
        return signals
    try:
        drv.get(url)
        WebDriverWait(drv, 25).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Match Odds')] | //*[contains(text(),'Over/Under')]"))
        )
        time.sleep(2)
    except Exception:
        return signals

    # назва матчу
    match_name = ""
    try:
        h1 = drv.find_elements(By.XPATH, "//h1")
        if h1:
            match_name = h1[0].text.strip()
    except Exception:
        pass
    if not match_name:
        try:
            match_name = drv.title.split("|")[0].strip()
        except Exception:
            match_name = "Football Match"

    # Match Odds
    try:
        mo_headers = drv.find_elements(By.XPATH, "//*[contains(text(),'Match Odds')][1]")
        if mo_headers:
            rows = drv.find_elements(By.XPATH, "//div[contains(@class,'runner-name')]/ancestor::div[contains(@class,'runner') or contains(@class,'selection')]")
            for row in rows:
                try:
                    name_el = row.find_element(By.XPATH, ".//div[contains(@class,'runner-name') or contains(@class,'selection-name')]")
                    name = name_el.text.strip()
                    price_el = None
                    for xp in [
                        ".//div[contains(@class,'back') and .//span[contains(@class,'price')]]//span[contains(@class,'price')]",
                        ".//button[contains(@class,'back-selection')]//span[contains(@class,'price')]",
                        ".//span[contains(@class,'odds')]"
                    ]:
                        try:
                            price_el = row.find_element(By.XPATH, xp)
                            break
                        except Exception:
                            continue
                    if not price_el:
                        continue
                    odds = safe_float(price_el.text.strip(), 0.0)
                    signals.append({
                        "site": "Betfair",
                        "match": match_name,
                        "prediction": name,
                        "bet_type": "Результат",
                        "confidence": 100,
                        "odds": odds
                    })
                except Exception:
                    continue
    except Exception:
        pass

    # Over/Under
    try:
        ou_headers = drv.find_elements(By.XPATH, "//*[contains(text(),'Over/Under')]")
        if ou_headers:
            ou_rows = drv.find_elements(By.XPATH, "//div[contains(@class,'runner-name') and (contains(.,'Over') or contains(.,'Under'))]/ancestor::div[contains(@class,'runner') or contains(@class,'selection')]")
            for row in ou_rows:
                try:
                    name = row.find_element(By.XPATH, ".//div[contains(@class,'runner-name') or contains(@class,'selection-name')]").text.strip()
                    price_el = None
                    for xp in [
                        ".//div[contains(@class,'back') and .//span[contains(@class,'price')]]//span[contains(@class,'price')]",
                        ".//button[contains(@class,'back-selection')]//span[contains(@class,'price')]",
                        ".//span[contains(@class,'odds')]"
                    ]:
                        try:
                            price_el = row.find_element(By.XPATH, xp)
                            break
                        except Exception:
                            continue
                    if not price_el:
                        continue
                    odds = safe_float(price_el.text.strip(), 0.0)
                    signals.append({
                        "site": "Betfair",
                        "match": match_name,
                        "prediction": name,  # "Over 2.5 Goals" / "Under 2.5 Goals"
                        "bet_type": "Тотал",
                        "confidence": 100,
                        "odds": odds
                    })
                except Exception:
                    continue
    except Exception:
        pass

    return signals

def get_betfair_signals(prev_data):
    """Забираємо перші ~10 подій і повертаємо нові/змінені сигнали."""
    out = []
    try:
        drv = ensure_driver()
        events = parse_betfair_market_cards(drv)
        if not events:
            return out
        for ev in events[:10]:
            ev_signals = open_event_and_collect_markets(drv, ev)
            for s in ev_signals:
                identifier = f"{s['site']}|{s['match']}|{s['prediction']}"
                if identifier not in prev_data or abs(prev_data[identifier]['odds'] - s['odds']) >= 0.05:
                    out.append(s)
                    prev_data[identifier] = {"confidence": s.get("confidence", 100), "odds": s['odds']}
            time.sleep(1.5)
    except Exception as e:
        logging.warning(f"[Betfair] parse error: {e}")
    return out

# ========= Надсилання =========
def send_to_all_users(msg: str):
    targets = USERS or ([int(ADMIN_CHAT_ID)] if ADMIN_CHAT_ID else [])
    for uid in targets:
        try:
            bot.send_message(uid, msg)
        except Exception as e:
            logging.error(f"Send error to {uid}: {e}")

def format_signal(s: dict) -> str:
    return (f"📌 Сайт: {s['site']}\n"
            f"⚽ Матч: {s['match']}\n"
            f"📊 Прогноз: {s['prediction']} ({s['bet_type']})\n"
            f"🔥 Впевненість: {s.get('confidence', 0)}%\n"
            f"💰 Коефіцієнт: {s.get('odds', 0)}")

def send_signals_loop():
    # Одноразовий тест при старті, якщо DEMO_MODE
    if DEMO_MODE:
        demo_id = "DEMO|Barcelona vs Real|Over 2.5"
        if demo_id not in sent_signals:
            demo = {"site": "DEMO", "match": "Barcelona vs Real Madrid", "prediction": "Over 2.5 Goals",
                    "bet_type": "Тотал", "confidence": 85, "odds": 1.75}
            send_to_all_users(format_signal(demo))
            sent_signals.add(demo_id)

    while True:
        try:
            all_signals = []

            # 1) HTML-сайти
            for site in sites:
                all_signals += parse_html_site(site, prev_signals_data)

            # 2) Betfair (Selenium)
            all_signals += get_betfair_signals(prev_signals_data)

            # 3) Файловий парсинг (для тесту, якщо вказано SAMPLE_DIR)
            if SAMPLE_DIR and os.path.isdir(SAMPLE_DIR):
                for fname in os.listdir(SAMPLE_DIR):
                    if fname.lower().endswith(".html"):
                        fp = os.path.join(SAMPLE_DIR, fname)
                        all_signals += parse_html_file(fp, site_name=f"FILE:{fname}")

            # Сортуємо і надсилаємо тільки нові (у межах цієї сесії)
            all_signals.sort(key=lambda x: (x.get('confidence', 0), x.get('odds', 0.0)), reverse=True)
            for s in all_signals:
                identifier = f"{s['site']}|{s['match']}|{s['prediction']}"
                if identifier in sent_signals:
                    continue
                send_to_all_users(format_signal(s))
                sent_signals.add(identifier)

            logging.info(f"Cycle done. New signals sent: {len(all_signals)}")
        except Exception as e:
            logging.error(f"Loop error: {e}")

        time.sleep(CHECK_INTERVAL_SEC)

# ========= Запуск фону =========
Thread(target=send_signals_loop, daemon=True).start()

# ========= Entry =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
