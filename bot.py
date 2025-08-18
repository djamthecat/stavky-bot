
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv

# Завантажуємо змінні середовища з .env
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Команда /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Привіт! Я бот для ставок. Буду надсилати сигнали 📊")

# Тестова функція сигналу
async def send_signal():
    match = "Барселона – Реал"
    market = "Тотал більше 2.5"
    percent = 73  # приклад >70%
    if percent >= 70:
        await bot.send_message(chat_id=CHAT_ID,
                               text=f"📢 Сигнал!\n{match}\n{market}: {percent}% грошей")

# Планувальник сигналів
async def scheduler():
    while True:
        await send_signal()
        await asyncio.sleep(300)  # кожні 5 хв

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)
