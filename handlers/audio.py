"""
Главный обработчик аудио:
  - приём файлов
  - inline-меню прямо на аудио-сообщении (как в slowreverbbot)
  - обработка и отправка результата с новыми кнопками
  - случайная реакция на сообщение пользователя
"""
import logging
import random
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Audio,
    BufferedInputFile,
    CallbackQuery,
    Document,
    Message,
    ReactionTypeEmoji,
    Voice,
)

from config.settings import settings
from services import EFFECTS, SUPPORTED_FORMATS, audio_processor
from utils.keyboards import effects_keyboard, processing_keyboard
from utils.states import AudioState

logger = logging.getLogger(__name__)
router = Router(name="audio")

# Пул реакций для случайного выбора
REACTION_POOL = ["❤️", "🔥", "🎉", "👏", "😍", "⚡", "🎵", "💯", "🤩", "😎"]


# ──────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────

def _get_file_info(message: Message) -> tuple[str, int, str] | None:
    if message.audio:
        obj: Audio = message.audio
        name = obj.file_name or f"audio_{uuid.uuid4().hex[:8]}.mp3"
        return obj.file_id, obj.file_size or 0, name

    if message.voice:
        obj: Voice = message.voice
        return obj.file_id, obj.file_size or 0, f"voice_{uuid.uuid4().hex[:8]}.ogg"

    if message.document:
        obj: Document = message.document
        name = obj.file_name or "file"
        ext = Path(name).suffix.lower()
        if ext in SUPPORTED_FORMATS:
            return obj.file_id, obj.file_size or 0, name

    return None


async def _download_file(bot: Bot, file_id: str, dest: Path) -> None:
    tg_file = await bot.get_file(file_id)
    await bot.download_file(tg_file.file_path, destination=str(dest))


async def _set_random_reaction(bot: Bot, chat_id: int, message_id: int) -> None:
    """Ставит случайную реакцию на сообщение пользователя."""
    emoji = random.choice(REACTION_POOL)
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(type="emoji", emoji=emoji)],
        )
    except Exception as exc:
        logger.debug("Не удалось поставить реакцию: %s", exc)


# ──────────────────────────────────────────────
#  Приём аудио → отправка с inline-меню
# ──────────────────────────────────────────────

@router.message(
    AudioState.waiting_for_file,
    F.content_type.in_({"audio", "voice", "document"}),
)
async def handle_audio(message: Message, state: FSMContext, bot: Bot) -> None:
    info = _get_file_info(message)

    if info is None:
        await message.answer(
            f"❌ Неподдерживаемый формат.\n"
            f"Принимаю: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )
        return

    file_id, file_size, filename = info

    if file_size > settings.MAX_FILE_SIZE_BYTES:
        size_mb = file_size / 1024 / 1024
        await message.answer(
            f"❌ Файл слишком большой ({size_mb:.1f} МБ).\n"
            f"Максимум — {settings.MAX_FILE_SIZE_MB} МБ."
        )
        return

    # Сохраняем в FSM
    await state.update_data(
        file_id=file_id,
        filename=filename,
        original_msg_id=message.message_id,
    )
    await state.set_state(AudioState.waiting_for_effect)

    # Ставим случайную реакцию на исходное сообщение пользователя
    await _set_random_reaction(bot, message.chat.id, message.message_id)

    # Пересылаем аудио обратно с inline-кнопками прямо на нём
    sent = await message.copy_to(
        chat_id=message.chat.id,
        reply_markup=effects_keyboard(),
    )

    # Сохраняем message_id нашего аудио-сообщения с кнопками
    await state.update_data(bot_audio_msg_id=sent.message_id)

    logger.info(
        "📥 Файл получен: user=%d | name=%s | size=%d B",
        message.from_user.id, filename, file_size,
    )


# ──────────────────────────────────────────────
#  Неверный документ
# ──────────────────────────────────────────────

@router.message(AudioState.waiting_for_file, F.document)
async def handle_wrong_document(message: Message) -> None:
    ext = Path(message.document.file_name or "").suffix.lower()
    await message.answer(
        f"❌ Формат {ext or 'неизвестен'} не поддерживается.\n"
        f"Поддерживаю: {', '.join(sorted(SUPPORTED_FORMATS))}"
    )


# ──────────────────────────────────────────────
#  Выбор эффекта — обработка
# ──────────────────────────────────────────────

@router.callback_query(AudioState.waiting_for_effect, F.data.startswith("effect:"))
async def handle_effect_choice(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    effect_key = callback.data.split(":", 1)[1]
    effect = EFFECTS.get(effect_key)

    if not effect:
        await callback.answer("Неизвестный эффект", show_alert=True)
        return

    data = await state.get_data()
    file_id: str | None = data.get("file_id")
    filename: str = data.get("filename", "audio.mp3")
    bot_audio_msg_id: int | None = data.get("bot_audio_msg_id")

    if not file_id:
        await callback.answer("Файл не найден, отправь снова.", show_alert=True)
        await state.set_state(AudioState.waiting_for_file)
        return

    await state.set_state(AudioState.processing)
    await callback.answer(f"⏳ {effect.emoji} {effect.label}...")

    # Меняем кнопки на заглушку "обрабатываю"
    if bot_audio_msg_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=bot_audio_msg_id,
                reply_markup=processing_keyboard(),
            )
        except TelegramBadRequest:
            pass

    input_path = Path(settings.TEMP_DIR) / f"{uuid.uuid4().hex}_{filename}"
    output_path: Path | None = None

    try:
        # Скачиваем оригинал
        await _download_file(bot, file_id, input_path)

        # Обрабатываем
        output_path = await audio_processor.process(input_path, effect)

        # Имя выходного файла
        stem = Path(filename).stem
        out_filename = f"{stem}_{effect.callback_data}.mp3"

        # Отправляем результат С новыми кнопками
        audio_bytes = output_path.read_bytes()
        bot_me = await bot.get_me()
        sent = await callback.message.answer_audio(
            audio=BufferedInputFile(audio_bytes, filename=out_filename),
            caption=f"{effect.emoji} {effect.label}  •  @{bot_me.username}",
            reply_markup=effects_keyboard(),
        )

        # Теперь у нас новое аудио с кнопками
        await state.update_data(
            file_id=file_id,
            filename=filename,
            bot_audio_msg_id=sent.message_id,
        )

        # Убираем кнопки со старого аудио
        if bot_audio_msg_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=callback.message.chat.id,
                    message_id=bot_audio_msg_id,
                    reply_markup=None,
                )
            except TelegramBadRequest:
                pass

        logger.info(
            "📤 Отправлен: user=%d | effect=%s | %.1f KB",
            callback.from_user.id, effect_key, len(audio_bytes) / 1024,
        )

    except TimeoutError as exc:
        logger.warning("Таймаут: user=%d", callback.from_user.id)
        await callback.message.answer(f"⏱️ {exc}")
        if bot_audio_msg_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=callback.message.chat.id,
                    message_id=bot_audio_msg_id,
                    reply_markup=effects_keyboard(),
                )
            except TelegramBadRequest:
                pass

    except Exception as exc:
        logger.exception("Ошибка обработки: user=%d", callback.from_user.id)
        await callback.message.answer(f"💥 Ошибка: {exc}\n\nПопробуй другой файл.")
        if bot_audio_msg_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=callback.message.chat.id,
                    message_id=bot_audio_msg_id,
                    reply_markup=effects_keyboard(),
                )
            except TelegramBadRequest:
                pass

    finally:
        audio_processor.cleanup(input_path)
        if output_path:
            audio_processor.cleanup(output_path)
        current = await state.get_state()
        if current == AudioState.processing:
            await state.set_state(AudioState.waiting_for_effect)


# ──────────────────────────────────────────────
#  Служебные callback-ы
# ──────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()
