"""
Speed Up & Slowed Bot — точка входа
"""
import asyncio
import logging
import shutil
import subprocess
import sys

# ──────────────────────────────────────────────────────────────────────────────
#  Авто-установка ffmpeg (нужно для BotHost.ru и других хостингов,
#  где нет возможности установить пакеты после деплоя вручную)
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_ffmpeg() -> None:
    """
    Проверяет наличие ffmpeg в системе.
    Если не найден — устанавливает через apt-get (Debian/Ubuntu).
    Завершает процесс с ошибкой, если установка не удалась.
    """
    if shutil.which("ffmpeg"):
        print("[ffmpeg] ✅ ffmpeg уже установлен, пропускаем.")
        return

    print("[ffmpeg] ⚙️  ffmpeg не найден — устанавливаю автоматически...")
    try:
        # Обновляем список пакетов
        subprocess.run(
            ["apt-get", "update", "-y"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        # Устанавливаем ffmpeg
        subprocess.run(
            ["apt-get", "install", "-y", "--no-install-recommends", "ffmpeg"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
        )
    except FileNotFoundError:
        print("[ffmpeg] ❌ apt-get не найден — установите ffmpeg вручную.")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.decode(errors="replace")
        print(f"[ffmpeg] ❌ Ошибка при установке:\n{err}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("[ffmpeg] ❌ Превышен таймаут установки ffmpeg.")
        sys.exit(1)

    # Финальная проверка
    if shutil.which("ffmpeg"):
        print("[ffmpeg] ✅ ffmpeg успешно установлен!")
    else:
        print("[ffmpeg] ❌ ffmpeg не найден даже после установки. Проверь права.")
        sys.exit(1)


# Вызываем ДО любых импортов, которые зависят от ffmpeg
_ensure_ffmpeg()

# ──────────────────────────────────────────────────────────────────────────────

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
