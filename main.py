import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
from db import Database
from handlers import router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logging.getLogger('aiogram').setLevel(logging.INFO)
logging.getLogger('asyncpg').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_DSN = os.getenv("DB_DSN")

if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не найдена в .env")
if not DB_DSN:
    raise ValueError("Переменная DB_DSN не найдена в .env")

async def main():
    db = Database(DB_DSN)
    try:
        await db.connect()
        logger.info("Подключение к PostgreSQL установлено")
    except Exception as e:
        logger.error(f"Ошибка подключения к PostgreSQL: {e}")
        return

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    router.db = db

    dp.include_router(router)

    logger.info(f"Запуск бота...")

    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Критическая ошибка при polling: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную (Ctrl+C)")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")
