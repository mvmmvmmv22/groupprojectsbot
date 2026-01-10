from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram import Bot
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
