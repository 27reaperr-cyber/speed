"""
Фабрика клавиатур для меню бота.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def effects_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура эффектов — крепится прямо к аудио-сообщению.
    Стиль как на скриншоте: широкие кнопки, по одной в ряд.
    """
    builder = InlineKeyboardBuilder()

    # Slowed
    builder.row(InlineKeyboardButton(text="🖥️  Slowed ×0.9",  callback_data="effect:slow_090"))
    builder.row(InlineKeyboardButton(text="🖥️  Slowed ×0.75", callback_data="effect:slow_075"))
    builder.row(InlineKeyboardButton(text="🖥️  Slowed ×0.5",  callback_data="effect:slow_050"))

    # Speed Up
    builder.row(InlineKeyboardButton(text="✨ Speed Up ×1.25", callback_data="effect:speed_125"))
    builder.row(InlineKeyboardButton(text="✨ Speed Up ×1.5",  callback_data="effect:speed_150"))
    builder.row(InlineKeyboardButton(text="✨ Speed Up ×2.0",  callback_data="effect:speed_200"))

    return builder.as_markup()


def processing_keyboard() -> InlineKeyboardMarkup:
    """Заглушка во время обработки."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏳ Обрабатываю...", callback_data="noop"))
    return builder.as_markup()

