import os
import requests
import telebot
from flask import Flask, request
from threading import Thread
import time
from bs4 import BeautifulSoup

TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(TOKEN)

USERS = []

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('UTF-8'))
    bot.process_new_updates([update])
    return "ok", 200

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    url = os.environ['RENDER_URL']
    s = bot.set_webhook(f"{url}/{TOKEN}")
    return "Webhook set!" if s else "Webhook failed!"

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id not in USERS:
        USERS.append(message.chat.id)
    bot.send_message(message.chat.id, "Привіт! Ти отримуватимеш сигнали ставок.")
    print("USERS:", USERS)

@bot.message_handler(commands=['stop'])
def stop(message):
    if message.chat.id in USERS:
        USERS.remove(message.chat.id)
    bot.send_message(message.chat.id, "Сигнали більше не надсилатимуться.")
    print("USERS:", USERS)

def get_inforadar_signals():
    url = "https://inforadar.live/"
    signals = []
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup.find_all('div', class_='signal'):
            match = s.find('span', class_='match').text.strip()
            prediction = s.find('span', class_='prediction').text.strip()
            confidence = s.find('span', class_='confidence').text.strip()
            signals.append({"site": "Inforadar", "match": match, "prediction": prediction, "confidence": confidence})
    except Exception as e:
        print("Error parsing Inforadar:", e)
    return signals

def get_betwatch_signals():
    url = "https://betwatch.fr/"
    signals = []
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup.find_all('div', class_='signal'):
            match = s.find('span', class_='match').text.strip()
            prediction = s.find('span', class_='prediction').text.strip()
            confidence = s.find('span', class_='confidence').text.strip()
            signals.append({"site": "Betwatch", "match": match, "prediction": prediction, "confidence": confidence})
    except Exception as e:
        print("Error parsing Betwatch:", e)
    return signals

def get_bet365_signals():
    url = "https://www.bet365.com/"
    signals = []
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup.find_all('div', class_='bet365-signal'):
            match = s.find('span', class_='bet365-match').text.strip()
            prediction = s.find('span', class_='bet365-prediction').text.strip()
            confidence = s.find('span', class_='bet365-confidence').text.strip()
            signals.append({"site": "Bet365", "match": match, "prediction": prediction, "confidence": confidence})
    except Exception as e:
        print("Error parsing Bet365:", e)
    return signals

def get_skybet_signals():
    url = "https://www.skybet.com/"
    signals = []
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup.find_all('div', class_='skybet-signal'):
            match = s.find('span', class_='skybet-match').text.strip()
            prediction = s.find('span', class_='skybet-prediction').text.strip()
            confidence = s.find('span', class_='skybet-confidence').text.strip()
            signals.append({"site": "Sky Bet", "match": match, "prediction": prediction, "confidence": confidence})
    except Exception as e:
        print("Error parsing Sky Bet:", e)
    return signals

def get_unibet_signals():
    url = "https://www.unibet.com/"
    signals = []
    try:
        r = requests.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup.find_all('div', class_='unibet-signal'):
            match = s.find('span', class_='unibet-match').text.strip()
            prediction = s.find('span', class_='unibet-prediction').text.strip()
            confidence = s.find('span', class_='unibet-confidence').text.strip()
            signals.append({"site": "Unibet", "match": match, "prediction": prediction, "confidence": confidence})
    except Exception as e:
        print("Error parsing Unibet:", e)
    return signals

sent_signals = set()

def send_signals():
    global sent_signals
    while True:
        all_signals = get_inforadar_signals() + get_betwatch_signals() + get_bet365_signals() + get_skybet_signals() + get_unibet_signals()
        print("Found signals:", all_signals)
        for s in all_signals:
            identifier = f"{s['site']}|{s['match']}|{s['prediction']}"
            if identifier not in sent_signals:
                msg = f"📌 Сайт: {s['site']}\n⚽ Матч: {s['match']}\n📊 Прогноз: {s['prediction']}\n🔥 Впевненість: {s['confidence']}"
                for user in USERS:
                    bot.send_message(user, msg)
                sent_signals.add(identifier)
        time.sleep(120)

Thread(target=send_signals).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
