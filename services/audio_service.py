"""
Сервис обработки аудио через ffmpeg.

Поддерживаемые операции:
  - speed_up / slowed  — изменение скорости с сохранением тональности (atempo)
  - pitch_up / pitch_down — изменение тональности без изменения темпа
"""
import asyncio
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AudioEffect:
    label: str          # отображаемое имя
    callback_data: str  # ключ для callback
    speed: float | None = None   # коэффициент скорости (atempo)
    pitch_steps: int | None = None  # шаги в полутонах (+ вверх, - вниз)


# Реестр всех эффектов
EFFECTS: dict[str, AudioEffect] = {
    "speed_125":   AudioEffect("🚀 Speed Up ×1.25",  "speed_125",  speed=1.25),
    "speed_150":   AudioEffect("🚀 Speed Up ×1.5",   "speed_150",  speed=1.50),
    "speed_200":   AudioEffect("🚀 Speed Up ×2.0",   "speed_200",  speed=2.00),
    "slow_075":    AudioEffect("🐌 Slowed ×0.75",    "slow_075",   speed=0.75),
    "slow_050":    AudioEffect("🐌 Slowed ×0.5",     "slow_050",   speed=0.50),
    "pitch_up2":   AudioEffect("🎵 Pitch +2",        "pitch_up2",  pitch_steps=2),
    "pitch_up4":   AudioEffect("🎵 Pitch +4",        "pitch_up4",  pitch_steps=4),
    "pitch_down2": AudioEffect("🎵 Pitch -2",        "pitch_down2", pitch_steps=-2),
    "pitch_down4": AudioEffect("🎵 Pitch -4",        "pitch_down4", pitch_steps=-4),
}

SUPPORTED_FORMATS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"}


def _build_atempo_chain(speed: float) -> str:
    """
    ffmpeg atempo допускает значения 0.5..2.0.
    Для значений вне диапазона строим цепочку фильтров.
    """
    filters = []
    remaining = speed

    if speed > 1.0:
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")
    else:
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")

    return ",".join(filters)


def _build_pitch_filter(semitones: int) -> str:
    """
    Изменение тональности через rubberband (если доступен) или
    через asetrate + atempo (compat fallback).

    asetrate меняет sample rate → воспринимается как pitch shift,
    затем atempo компенсирует скорость воспроизведения.
    """
    factor = 2 ** (semitones / 12)            # мультипликатор частоты
    atempo_compensation = 1.0 / factor        # компенсация скорости

    asetrate = f"asetrate=44100*{factor:.6f}"
    aresample = "aresample=44100"
    atempo = _build_atempo_chain(atempo_compensation)

    return f"{asetrate},{aresample},{atempo}"


class AudioProcessor:
    def __init__(self) -> None:
        self.temp_dir = Path(settings.TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._verify_ffmpeg()

    @staticmethod
    def _verify_ffmpeg() -> None:
        if not shutil.which("ffmpeg"):
            raise EnvironmentError(
                "❌ ffmpeg не найден. Установите его: sudo apt install ffmpeg"
            )
        logger.info("✅ ffmpeg обнаружен в системе")

    def _tmp_path(self, suffix: str = ".mp3") -> Path:
        return self.temp_dir / f"{uuid.uuid4().hex}{suffix}"

    async def process(
        self,
        input_path: Path,
        effect: AudioEffect,
    ) -> Path:
        """Применяет эффект и возвращает путь к результату."""
        output_path = self._tmp_path(".mp3")

        if effect.speed is not None:
            af = _build_atempo_chain(effect.speed)
        elif effect.pitch_steps is not None:
            af = _build_pitch_filter(effect.pitch_steps)
        else:
            raise ValueError(f"Эффект '{effect.label}' не содержит параметров")

        cmd = [
            "ffmpeg",
            "-y",                          # перезапись без вопросов
            "-i", str(input_path),
            "-filter:a", af,
            "-acodec", "libmp3lame",
            "-q:a", "2",                   # качество VBR ~190kbps
            str(output_path),
        ]

        logger.info(
            "⚙️  Обработка: effect=%s | af=%s | out=%s",
            effect.label, af, output_path.name,
        )

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=settings.PROCESSING_TIMEOUT,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.PROCESSING_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("⏱️  Превышен таймаут обработки (%ds)", settings.PROCESSING_TIMEOUT)
            output_path.unlink(missing_ok=True)
            raise TimeoutError(
                f"Обработка превысила {settings.PROCESSING_TIMEOUT} секунд. "
                "Попробуйте файл поменьше."
            )

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            logger.error("❌ ffmpeg вернул код %d:\n%s", proc.returncode, err_msg)
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"Ошибка ffmpeg (код {proc.returncode})")

        logger.info("✅ Обработка завершена: %s (%.1f KB)", output_path.name, output_path.stat().st_size / 1024)
        return output_path

    @staticmethod
    def cleanup(*paths: Path) -> None:
        """Удаляет временные файлы."""
        for p in paths:
            try:
                p.unlink(missing_ok=True)
                logger.debug("🗑️  Удалён: %s", p.name)
            except Exception as exc:
                logger.warning("⚠️  Не удалось удалить %s: %s", p, exc)


audio_processor = AudioProcessor()
