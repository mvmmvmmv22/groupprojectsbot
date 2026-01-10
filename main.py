import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
from db import Database
from handlers_commands import *
from handlers_actions import router
import logger
from bot import bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logging.getLogger('aiogram').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

load_dotenv()

DB_DSN = os.getenv("DB_DSN")

if not DB_DSN:
    raise ValueError("Переменная DB_DSN не найдена в .env")


async def check_deadlines(bot: Bot, db: Database):
    logger.info("Фоновый таск запущен")
    while True:
        try:
            projects = await db.get_projects_near_deadline()
            for p in projects:
                hours_left = (p["deadline"] - datetime.utcnow()).total_seconds() // 3600
                try:
                    await bot.send_message(
                        p["creator_id"],
                        f"⚠️ Проект «{p['title']}»: дедлайн через {int(hours_left)} ч."
                    )
                    await db.set_last_notification(p["id"], datetime.utcnow())
                    logger.info("Уведомление отправлено project_id=%d, user_id=%d", p["id"], p["creator_id"])
                except Exception as e:
                    logger.error("Не удалось отправить user_id=%d: %s", p["creator_id"], e)
        except Exception as e:
            logger.error("Ошибка фонового таска: %s", e)
        await asyncio.sleep(1800)


async def main():
    db = Database(DB_DSN)
    await db.connect()

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    router.db = db

    dp.include_router(router)

    logger.info(f"Запуск бота...")
    asyncio.create_task(check_deadlines(bot, db))
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
