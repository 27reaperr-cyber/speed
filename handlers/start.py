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

WELCOME_TEXT = """В этом боте ты сможешь обработать трек при помощи одного из заданных пресетов:
• Slowed;
• Speed Up;

Чтобы начать пользоваться ботом:
• Отправь файл в формате .mp3;

• Перешли голосовое сообщение.

Другие проекты: @dreinnh"""


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AudioState.waiting_for_file)
    await message.answer(WELCOME_TEXT)
    logger.info("👤 Пользователь %d запустил бота", message.from_user.id)
