# TODO: медиа. системный промпт/ИИ


import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger
from handlers import router



load_dotenv()
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
bot = Bot(token=os.getenv("BOT_TOKEN"))

os.makedirs("logs", exist_ok=True)
logger.add("logs/bot_{time}.log", level="DEBUG", rotation="10 MB", retention="1 month", compression="gz")

async def main():
    try:
        logger.info("Starting bot...")
        await bot.delete_webhook(drop_pending_updates=True)
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Unknown error while stoping from panel: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())