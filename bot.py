"""
Speed Up & Slowed Bot — точка входа
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config.settings import settings
from handlers import audio, start, errors
from middlewares.throttle import ThrottlingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("🚀 Запуск Speed Up & Slowed Bot...")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Middlewares
    dp.message.middleware(ThrottlingMiddleware(rate_limit=3.0))

    # Routers
    dp.include_router(start.router)
    dp.include_router(audio.router)
    dp.include_router(errors.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Бот запущен. Слушаю обновления...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("❌ Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
