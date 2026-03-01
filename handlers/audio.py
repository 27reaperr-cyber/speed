"""
Главный обработчик аудио:
  - приём файлов
  - показ меню эффектов
  - обработка и отправка результата
"""
import logging
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
    Voice,
)

from config.settings import settings
from services import EFFECTS, SUPPORTED_FORMATS, audio_processor
from utils.keyboards import back_keyboard, main_menu_keyboard
from utils.states import AudioState

logger = logging.getLogger(__name__)
router = Router(name="audio")

# ──────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────

def _get_file_info(message: Message) -> tuple[str, int, str] | None:
    """
    Возвращает (file_id, file_size, original_filename) или None.
    Поддерживает audio, voice, document.
    """
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


# ──────────────────────────────────────────────
#  Приём аудио
# ──────────────────────────────────────────────

@router.message(
    AudioState.waiting_for_file,
    F.content_type.in_({"audio", "voice", "document"}),
)
async def handle_audio(message: Message, state: FSMContext, bot: Bot) -> None:
    info = _get_file_info(message)

    if info is None:
        await message.answer(
            "❌ <b>Неподдерживаемый формат.</b>\n\n"
            f"Принимаю: {', '.join(sorted(SUPPORTED_FORMATS))}",
            reply_markup=None,
        )
        return

    file_id, file_size, filename = info

    if file_size > settings.MAX_FILE_SIZE_BYTES:
        size_mb = file_size / 1024 / 1024
        await message.answer(
            f"❌ <b>Файл слишком большой</b> ({size_mb:.1f} МБ).\n"
            f"Максимум — {settings.MAX_FILE_SIZE_MB} МБ."
        )
        return

    # Сохраняем данные в FSM
    await state.update_data(
        file_id=file_id,
        filename=filename,
    )
    await state.set_state(AudioState.waiting_for_effect)

    await message.answer(
        f"✅ Файл <b>{filename}</b> получен!\n\n"
        "Выбери эффект 👇",
        reply_markup=main_menu_keyboard(),
    )
    logger.info(
        "📥 Файл получен: user=%d | name=%s | size=%d bytes",
        message.from_user.id, filename, file_size,
    )


# ──────────────────────────────────────────────
#  Неверный формат (документ с недопустимым расширением)
# ──────────────────────────────────────────────

@router.message(
    AudioState.waiting_for_file,
    F.document,
)
async def handle_wrong_document(message: Message) -> None:
    ext = Path(message.document.file_name or "").suffix.lower()
    await message.answer(
        f"❌ Формат <code>{ext or 'неизвестен'}</code> не поддерживается.\n\n"
        f"Поддерживаю: {', '.join(sorted(SUPPORTED_FORMATS))}"
    )


# ──────────────────────────────────────────────
#  Обработка выбора эффекта
# ──────────────────────────────────────────────

@router.callback_query(AudioState.waiting_for_effect, F.data.startswith("effect:"))
async def handle_effect_choice(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    effect_key = callback.data.split(":", 1)[1]
    effect = EFFECTS.get(effect_key)

    if not effect:
        await callback.answer("⚠️ Неизвестный эффект", show_alert=True)
        return

    data = await state.get_data()
    file_id: str = data.get("file_id")
    filename: str = data.get("filename", "audio.mp3")

    if not file_id:
        await callback.message.answer("❌ Файл не найден. Отправь аудио заново.")
        await state.set_state(AudioState.waiting_for_file)
        await callback.answer()
        return

    await state.set_state(AudioState.processing)
    await callback.answer()

    # Уведомление о начале обработки
    status_msg = await callback.message.edit_text(
        f"⏳ Обрабатываю: <b>{effect.label}</b>\n"
        f"Файл: <code>{filename}</code>\n\n"
        "Это займёт несколько секунд...",
        reply_markup=None,
    )

    input_path = Path(settings.TEMP_DIR) / f"{uuid.uuid4().hex}_{filename}"
    output_path: Path | None = None

    try:
        # Скачиваем файл
        logger.info(
            "⬇️  Скачиваю: user=%d | file_id=%s",
            callback.from_user.id, file_id,
        )
        await _download_file(bot, file_id, input_path)

        # Применяем эффект
        output_path = await audio_processor.process(input_path, effect)

        # Формируем имя выходного файла
        stem = Path(filename).stem
        out_filename = f"{stem}_{effect.callback_data}.mp3"

        # Читаем и отправляем
        audio_bytes = output_path.read_bytes()
        await callback.message.answer_audio(
            audio=BufferedInputFile(audio_bytes, filename=out_filename),
            caption=(
                f"✅ Готово!\n"
                f"🎛 Эффект: <b>{effect.label}</b>\n"
                f"📁 Файл: <code>{out_filename}</code>"
            ),
        )

        # Обновляем статус
        await status_msg.edit_text(
            "✅ Обработка завершена! Файл отправлен выше ⬆️\n\n"
            "Отправь ещё аудио или выбери новый файл.",
        )

        logger.info(
            "📤 Отправлен: user=%d | effect=%s | size=%.1f KB",
            callback.from_user.id, effect_key, len(audio_bytes) / 1024,
        )

    except TimeoutError as exc:
        logger.warning("⏱️  Таймаут: user=%d | %s", callback.from_user.id, exc)
        await status_msg.edit_text(
            f"⏱️ <b>Превышено время обработки!</b>\n{exc}",
            reply_markup=back_keyboard(),
        )

    except Exception as exc:
        logger.exception("💥 Ошибка обработки: user=%d", callback.from_user.id)
        await status_msg.edit_text(
            f"💥 <b>Произошла ошибка:</b>\n<code>{exc}</code>\n\n"
            "Попробуй другой файл.",
            reply_markup=back_keyboard(),
        )

    finally:
        # Удаляем временные файлы
        audio_processor.cleanup(input_path)
        if output_path:
            audio_processor.cleanup(output_path)
        # Возвращаем состояние
        await state.set_state(AudioState.waiting_for_file)
        await state.update_data(file_id=None, filename=None)


# ──────────────────────────────────────────────
#  Служебные callback-ы
# ──────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AudioState.waiting_for_file)
    try:
        await callback.message.edit_text("❌ Отменено. Отправь новый аудиофайл.")
    except TelegramBadRequest:
        pass
    await callback.answer("Отменено")


@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    file_id = data.get("file_id")

    if file_id:
        await state.set_state(AudioState.waiting_for_effect)
        try:
            await callback.message.edit_text(
                "📂 Файл всё ещё у меня. Выбери эффект 👇",
                reply_markup=main_menu_keyboard(),
            )
        except TelegramBadRequest:
            pass
    else:
        await state.set_state(AudioState.waiting_for_file)
        try:
            await callback.message.edit_text(
                "📂 Отправь аудиофайл, чтобы начать."
            )
        except TelegramBadRequest:
            pass

    await callback.answer()
