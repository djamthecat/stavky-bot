
import os
import asyncio
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv

# Завантажуємо змінні середовища
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Команда /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Привіт! Я бот для ставок. Буду надсилати сигнали з сайту!")

# Функція парсингу сайту
def get_signals():
    signals = []
    url = "https://www.inforadar.live/matches"  # приклад
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Приклад: знаходимо всі матчі та їх відсотки на тотали
        matches = soup.find_all("div", class_="match-row")
        for match in matches:
            team1 = match.find("div", class_="team1").text.strip()
            team2 = match.find("div", class_="team2").text.strip()
            total_percent = match.find("span", class_="total-percent").text.strip().replace("%","")
            try:
                total_percent = int(total_percent)
                if total_percent >= 70:
                    signals.append(f"📢 {team1} – {team2} | Тотал більше 2.5: {total_percent}%")
            except:
                continue
    return signals

# Планувальник сигналів
async def send_signals():
    signals = get_signals()
    for signal in signals:
        await bot.send_message(chat_id=CHAT_ID, text=signal)

async def scheduler():
    while True:
        await send_signals()
        await asyncio.sleep(300)  # кожні 5 хв

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)
