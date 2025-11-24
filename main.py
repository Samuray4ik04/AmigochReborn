import subprocess
import sys
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
import asyncio
from loguru import logger
from handlers import router


load_dotenv()
bot = Bot(os.getenv("BOT_TOKEN"))
dp = Dispatcher()

os.makedirs("logs", exist_ok=True)
logger.add("logs/bot_{time}.log", level="DEBUG", rotation="10 MB", retention="1 month", compression="gz")

async def main():
    try:
        logger.info("Starting bot...")
        await bot.delete_webhook(drop_pending_updates=True)
        dp.include_router(router)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped from panel")