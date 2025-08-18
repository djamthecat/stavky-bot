import os
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
    await message.answer("Бот працює ✅")

# Команда /check для перевірки токена і chat_id
@dp.message_handler(commands=["check"])
async def check(message: types.Message):
    await message.answer(f"API_TOKEN: {API_TOKEN}\nCHAT_ID: {CHAT_ID}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
