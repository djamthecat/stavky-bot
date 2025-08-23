import os
import requests
import telebot
from flask import Flask, request
from threading import Thread
import time
from bs4 import BeautifulSoup

TOKEN = os.environ['TOKEN']  # Telegram токен
bot = telebot.TeleBot(TOKEN)

USERS = []

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    url = os.environ['RENDER_URL']  # Твоє доменне ім'я Render
    s = bot.set_webhook(f"{url}/{TOKEN}")
    return "Webhook set!" if s else "Webhook failed!"

# Команди Telegram
@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id not in USERS:
        USERS.append(message.chat.id)
    bot.send_message(message.chat.id, "Привіт! Ти отримуватимеш сигнали ставок.")

@bot.message_handler(commands=['stop'])
def stop(message):
    if message.chat.id in USERS:
        USERS.remove(message.chat.id)
    bot.send_message(message.chat.id, "Сигнали більше не надсилатимуться.")

# Парсер inforadar.live
def get_signals():
    url = "https://inforadar.live/"
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        signals = []
        for signal in soup.find_all(class_='signal'):
            match = signal.find(class_='match').text.strip()
            prediction = signal.find(class_='prediction').text.strip()
            confidence = signal.find(class_='confidence').text.strip()
            signals.append({"match": match, "prediction": prediction, "confidence": confidence})
        return signals
    except:
        return []

def send_signals():
    while True:
        signals = get_signals()
        for s in signals:
            msg = f"⚽ Матч: {s['match']}\n📊 Прогноз: {s['prediction']}\n🔥 Впевненість: {s['confidence']}"
            for user in USERS:
                bot.send_message(user, msg)
        time.sleep(3600)

Thread(target=send_signals).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
