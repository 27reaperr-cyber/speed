"""
Глобальная обработка ошибок и неожиданных апдейтов.
"""
import logging

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message

from utils.states import AudioState

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.errors(ExceptionTypeFilter(Exception))
async def global_error_handler(event: ErrorEvent) -> bool:
    logger.exception(
        "💥 Необработанное исключение: update_id=%s",
        getattr(event.update, "update_id", "?"),
        exc_info=event.exception,
    )
    return True  # Помечаем как обработанное


# Хендлер для любых текстовых сообщений вне ожидаемого состояния
@router.message()
async def handle_unexpected(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await state.set_state(AudioState.waiting_for_file)

    await message.answer(
        "🎵 Отправь аудиофайл для обработки.\n"
        "Используй /start чтобы начать заново."
    )
