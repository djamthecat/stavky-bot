import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import asyncio

API_TOKEN = 'YOUR_BOT_API_TOKEN'
API_KEY = 'YOUR_BETWATCH_API_KEY'
CHAT_ID = 'YOUR_CHAT_ID'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

async def fetch_betting_data():
    url = f"https://api.betwatch.fr/api/v1/football/live?api_key={API_KEY}"
    response = requests.get(url)
    data = response.json()
    return data

async def send_betting_signal():
    data = await fetch_betting_data()
    for match in data:
        for market in match['markets']:
            if market['name'] == 'Over/Under 2.5 Goals':
                for runner in market['runners']:
                    if runner['volume'] > 10000:  # Фільтр за обсягом ставок
                        message = f"Матч: {match['teams']['v1']} vs {match['teams']['v2']}\n"
                        message += f"Тотал: {runner['name']}\n"
                        message += f"Коефіцієнт: {runner['odd']}\n"
                        message += f"Обсяг ставок: {runner['volume']}\n"
                        await bot.send_message(chat_id=CHAT_ID, text=message)

async def scheduler():
    while True:
        await send_betting_signal()
        await asyncio.sleep(300)  # Перевірка кожні 5 хвилин

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
