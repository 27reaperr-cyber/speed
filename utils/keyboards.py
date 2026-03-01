"""
Фабрика клавиатур для меню бота.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Speed Up
    builder.row(
        InlineKeyboardButton(text="━━━ 🚀 SPEED UP ━━━", callback_data="noop"),
    )
    builder.row(
        InlineKeyboardButton(text="×1.25",  callback_data="effect:speed_125"),
        InlineKeyboardButton(text="×1.5",   callback_data="effect:speed_150"),
        InlineKeyboardButton(text="×2.0",   callback_data="effect:speed_200"),
    )

    # Slowed
    builder.row(
        InlineKeyboardButton(text="━━━ 🐌 SLOWED ━━━", callback_data="noop"),
    )
    builder.row(
        InlineKeyboardButton(text="×0.75",  callback_data="effect:slow_075"),
        InlineKeyboardButton(text="×0.5",   callback_data="effect:slow_050"),
    )

    # Pitch
    builder.row(
        InlineKeyboardButton(text="━━━ 🎵 PITCH ━━━", callback_data="noop"),
    )
    builder.row(
        InlineKeyboardButton(text="▲ +2 полутона",  callback_data="effect:pitch_up2"),
        InlineKeyboardButton(text="▲ +4 полутона",  callback_data="effect:pitch_up4"),
    )
    builder.row(
        InlineKeyboardButton(text="▼ -2 полутона",  callback_data="effect:pitch_down2"),
        InlineKeyboardButton(text="▼ -4 полутона",  callback_data="effect:pitch_down4"),
    )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )

    return builder.as_markup()


def back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu"))
    return builder.as_markup()
