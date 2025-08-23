import os
import time
import telebot
from flask import Flask, request
from threading import Thread
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

TOKEN = os.environ['TOKEN']
RENDER_URL = os.environ['RENDER_URL']
bot = telebot.TeleBot(TOKEN)
USERS = []

app = Flask(__name__)

# --- Flask routes ---
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

# --- Telegram handlers ---
@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id not in USERS:
        USERS.append(message.chat.id)
    bot.send_message(message.chat.id, "Привіт! Ти отримуватимеш футбольні сигнали (1X2, тотали, фори).")
    print("USERS:", USERS)

@bot.message_handler(commands=['stop'])
def stop(message):
    if message.chat.id in USERS:
        USERS.remove(message.chat.id)
    bot.send_message(message.chat.id, "Сигнали більше не надсилатимуться.")
    print("USERS:", USERS)

# --- Список сайтів ---
sites = [
    {"name": "Inforadar", "url": "https://inforadar.live/", "signal_class": "signal"},
    {"name": "Betwatch", "url": "https://betwatch.fr/", "signal_class": "signal"},
    {"name": "SkyBet", "url": "https://www.skybet.com/football", "signal_class": "signal"},
    {"name": "Unibet", "url": "https://www.unibet.com/betting/football", "signal_class": "signal"},
]

prev_signals_data = {}  # попередні сигнали

# --- Визначення типу ставки ---
def get_bet_type(prediction):
    pred = prediction.lower()
    if any(x in pred for x in ["over", "under", "тотал"]):
        return "Тотал"
    elif any(x in pred for x in ["фора", "+", "-"]):
        return "Фора"
    elif any(x in pred for x in ["1", "x", "2"]):
        return "Результат"
    else:
        return "Інше"

# --- HTML-парсинг ---
def get_site_signals(site, prev_data):
    signals = []
    try:
        r = requests.get(site['url'], timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup.find_all('div', class_=site['signal_class']):
            match_tag = s.find('span', class_='match')
            prediction_tag = s.find('span', class_='prediction')
            confidence_tag = s.find('span', class_='confidence')
            odds_tag = s.find('span', class_='odds')
            if not match_tag or not prediction_tag:
                continue
            match = match_tag.text.strip()
            prediction = prediction_tag.text.strip()
            bet_type = get_bet_type(prediction)
            confidence = int(confidence_tag.text.strip().replace('%','')) if confidence_tag else 0
            odds = float(odds_tag.text.strip()) if odds_tag else 0
            identifier = f"{site['name']}|{match}|{prediction}"
            if identifier not in prev_data or abs(prev_data[identifier]['confidence'] - confidence) >= 5 or abs(prev_data[identifier]['odds'] - odds) >= 0.05:
                signals.append({"site": site['name'], "match": match, "prediction": prediction, "bet_type": bet_type, "confidence": confidence, "odds": odds})
                prev_data[identifier] = {"confidence": confidence, "odds": odds}
    except Exception as e:
        print(f"Error parsing {site['name']}: {e}")
    return signals

# --- Selenium для Betfair ---
def get_betfair_signals(prev_data):
    signals = []
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
        driver.get("https://www.betfair.com/exchange/football")
        time.sleep(5)

        events = driver.find_elements(By.CLASS_NAME, "market-wrapper")
        for event in events:
            match_tag = event.find_element(By.CLASS_NAME, "market-name")
            match = match_tag.text.strip()
            outcomes = event.find_elements(By.CLASS_NAME, "runner")
            for o in outcomes:
                pred_tag = o.find_element(By.CLASS_NAME, "runner-name")
                odds_tag = o.find_element(By.CLASS_NAME, "odds")
                market_tag = o.find_element(By.CLASS_NAME, "market-type")
                prediction = pred_tag.text.strip()
                odds = float(odds_tag.text.strip())
                market_type = market_tag.text.strip()
                bet_type = "Результат" if market_type=="MATCH_ODDS" else "Тотал" if market_type=="TOTAL_GOALS" else "Фора"
                identifier = f"Betfair|{match}|{prediction}"
                if identifier not in prev_data or abs(prev_data[identifier]['odds'] - odds) >= 0.05:
                    signals.append({"site": "Betfair", "match": match, "prediction": prediction, "bet_type": bet_type, "confidence": 100, "odds": odds})
                    prev_data[identifier] = {"confidence": 100, "odds": odds}
        driver.quit()
    except Exception as e:
        print("Error parsing Betfair:", e)
    return signals

# --- Надсилання сигналів ---
def send_signals():
    while True:
        all_signals = []
        for site in sites:
            all_signals += get_site_signals(site, prev_signals_data)
        all_signals += get_betfair_signals(prev_signals_data)
        all_signals.sort(key=lambda x: (x['confidence'], x['odds']), reverse=True)
        for s in all_signals:
            msg = (f"📌 Сайт: {s['site']}\n⚽ Матч: {s['match']}\n"
                   f"📊 Прогноз: {s['prediction']} ({s['bet_type']})\n"
                   f"🔥 Впевненість: {s['confidence']}%\n💰 Коефіцієнт: {s['odds']}")
            for user in USERS:
                try:
                    bot.send_message(user, msg)
                except Exception as e:
                    print(f"Error sending to {user}: {e}")
        time.sleep(120)

Thread(target=send_signals).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
