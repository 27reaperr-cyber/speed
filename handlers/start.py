"""
Обработчик команды /start и /help.
"""
import logging

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from utils.states import AudioState

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_TEXT = """
🎧 <b>Speed Up &amp; Slowed Bot</b>

Привет! Я умею обрабатывать аудиофайлы:

🚀 <b>Speed Up</b> — ускорение (×1.25 / ×1.5 / ×2.0)
🐌 <b>Slowed</b>   — замедление (×0.75 / ×0.5)
🎵 <b>Pitch</b>    — тональность (±2 / ±4 полутона)

<b>Как использовать:</b>
1. Отправь аудиофайл (MP3, WAV, OGG, M4A...)
2. Выбери эффект в меню
3. Получи обработанный файл ✨

⚠️ Максимальный размер файла — <b>50 МБ</b>

Отправь аудио — и погнали! 🎶
"""


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AudioState.waiting_for_file)
    await message.answer(WELCOME_TEXT)
    logger.info("👤 Пользователь %d запустил бота", message.from_user.id)
