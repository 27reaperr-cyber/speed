"""
Главный обработчик аудио:
  - приём .mp3 / .m4a / .wav / .ogg / .flac / .aac — как audio и как document
  - приём голосовых сообщений (voice)
  - работает в ЛЮБОМ состоянии FSM (не требует /start)
  - inline-меню прямо на аудио-сообщении
  - случайная реакция на сообщение пользователя
"""
import logging
import random
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
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

# Состояния, в которых принимаем новые файлы
ACCEPT_STATES = StateFilter(AudioState.waiting_for_file, AudioState.waiting_for_effect, None)


# ──────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────

def _get_file_info(message: Message) -> tuple[str, int, str] | None:
    """
    Возвращает (file_id, file_size, filename) или None.
    Обрабатывает: audio, voice, document с поддерживаемым расширением.
    """
    # Аудиофайл (Telegram определил как музыку)
    if message.audio:
        obj: Audio = message.audio
        name = obj.file_name or f"audio_{uuid.uuid4().hex[:8]}.mp3"
        return obj.file_id, obj.file_size or 0, name

    # Голосовое сообщение (всегда .ogg opus)
    if message.voice:
        obj: Voice = message.voice
        return obj.file_id, obj.file_size or 0, f"voice_{uuid.uuid4().hex[:8]}.ogg"

    # Документ — проверяем расширение
    if message.document:
        obj: Document = message.document
        name = obj.file_name or "file.mp3"
        ext = Path(name).suffix.lower()
        if ext in SUPPORTED_FORMATS:
            return obj.file_id, obj.file_size or 0, name

    return None


def _is_unsupported_document(message: Message) -> bool:
    """True только если это документ с неподдерживаемым расширением."""
    if not message.document:
        return False
    name = message.document.file_name or ""
    ext = Path(name).suffix.lower()
    return ext not in SUPPORTED_FORMATS


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
#  Приём аудио — работает в ЛЮБОМ состоянии
# ──────────────────────────────────────────────

@router.message(
    ACCEPT_STATES,
    F.content_type.in_({"audio", "voice", "document"}),
)
async def handle_audio(message: Message, state: FSMContext, bot: Bot) -> None:
    info = _get_file_info(message)

    # Документ с неподдерживаемым расширением
    if info is None:
        if message.document:
            ext = Path(message.document.file_name or "").suffix.lower()
            await message.answer(
                f"❌ Формат <code>{ext or 'неизвестен'}</code> не поддерживается.\n\n"
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

    # Обновляем состояние
    await state.update_data(
        file_id=file_id,
        filename=filename,
        original_msg_id=message.message_id,
    )
    await state.set_state(AudioState.waiting_for_effect)

    # Случайная реакция на сообщение пользователя
    await _set_random_reaction(bot, message.chat.id, message.message_id)

    # Копируем аудио обратно с inline-кнопками прямо на нём
    sent = await message.copy_to(
        chat_id=message.chat.id,
        reply_markup=effects_keyboard(),
    )

    await state.update_data(bot_audio_msg_id=sent.message_id)

    logger.info(
        "📥 Файл получен: user=%d | name=%s | size=%d B | type=%s",
        message.from_user.id, filename, file_size, message.content_type,
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

    # Кнопки → заглушка "обрабатываю"
    if bot_audio_msg_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=bot_audio_msg_id,
                reply_markup=processing_keyboard(),
            )
        except TelegramBadRequest:
            pass

    # Определяем расширение для сохранения: голосовые → .ogg, остальные как есть
    src_ext = Path(filename).suffix.lower() or ".mp3"
    input_path = Path(settings.TEMP_DIR) / f"{uuid.uuid4().hex}{src_ext}"
    output_path: Path | None = None

    try:
        # Скачиваем оригинал
        await _download_file(bot, file_id, input_path)

        # Обрабатываем
        output_path = await audio_processor.process(input_path, effect)

        # Имя выходного файла
        stem = Path(filename).stem
        out_filename = f"{stem}_{effect.callback_data}.mp3"

        # Отправляем результат с кнопками
        audio_bytes = output_path.read_bytes()
        bot_me = await bot.get_me()
        sent = await callback.message.answer_audio(
            audio=BufferedInputFile(audio_bytes, filename=out_filename),
            caption=f"{effect.emoji} {effect.label}  •  @{bot_me.username}",
            reply_markup=effects_keyboard(),
        )

        # Обновляем msg_id — теперь кнопки на новом аудио
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
