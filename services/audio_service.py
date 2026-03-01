"""
Сервис обработки аудио через ffmpeg.

Режим: виниловый эффект — скорость и тональность меняются вместе.
Используется asetrate (изменяет sample rate → меняет и темп и pitch одновременно),
затем aresample для нормализации обратно в 44100 Hz.
"""
import asyncio
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)

BASE_RATE = 44100  # стандартная частота дискретизации


@dataclass
class AudioEffect:
    label: str           # отображаемое имя
    callback_data: str   # ключ для callback
    speed: float         # множитель скорости (и тональности)
    emoji: str = "🎵"


# Реестр эффектов — только скорость (pitch идёт автоматически)
EFFECTS: dict[str, AudioEffect] = {
    "speed_125": AudioEffect("Speed Up ×1.25",  "speed_125", speed=1.25, emoji="✨"),
    "speed_150": AudioEffect("Speed Up ×1.5",   "speed_150", speed=1.50, emoji="✨"),
    "speed_200": AudioEffect("Speed Up ×2.0",   "speed_200", speed=2.00, emoji="✨"),
    "slow_090":  AudioEffect("Slowed ×0.9",     "slow_090",  speed=0.90, emoji="🖥️"),
    "slow_075":  AudioEffect("Slowed ×0.75",    "slow_075",  speed=0.75, emoji="🖥️"),
    "slow_050":  AudioEffect("Slowed ×0.5",     "slow_050",  speed=0.50, emoji="🖥️"),
}

SUPPORTED_FORMATS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"}


def _build_vinyl_filter(speed: float) -> str:
    """
    Виниловый эффект: asetrate меняет sample rate пропорционально скорости,
    aresample возвращает выходной поток к стандартным 44100 Hz.
    Результат: трек звучит быстрее/медленнее И выше/ниже по тональности —
    точно как при изменении скорости пластинки или кассеты.
    """
    new_rate = int(BASE_RATE * speed)
    return f"asetrate={new_rate},aresample={BASE_RATE}"


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

    async def process(self, input_path: Path, effect: AudioEffect) -> Path:
        """Применяет виниловый эффект и возвращает путь к результату."""
        output_path = self._tmp_path(".mp3")
        af = _build_vinyl_filter(effect.speed)

        # -vn убирает видео/обложку (иначе ошибка на .m4a с картинкой)
        # -ar / -ac нормализуют выход в стерео 44100 Hz
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-vn",
            "-filter:a", af,
            "-acodec", "libmp3lame",
            "-q:a", "2",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]

        logger.info(
            "⚙️  Обработка: effect=%s | af=%s | out=%s",
            effect.label, af, output_path.name,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.PROCESSING_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("⏱️  Превышен таймаут (%ds)", settings.PROCESSING_TIMEOUT)
            output_path.unlink(missing_ok=True)
            raise TimeoutError(
                f"Обработка превысила {settings.PROCESSING_TIMEOUT} секунд. "
                "Попробуйте файл поменьше."
            )

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            logger.error("❌ ffmpeg код %d:\n%s", proc.returncode, err_msg)
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"Ошибка ffmpeg (код {proc.returncode})")

        logger.info(
            "✅ Готово: %s (%.1f KB)",
            output_path.name, output_path.stat().st_size / 1024,
        )
        return output_path

    @staticmethod
    def cleanup(*paths: Path) -> None:
        for p in paths:
            try:
                p.unlink(missing_ok=True)
                logger.debug("🗑️  Удалён: %s", p.name)
            except Exception as exc:
                logger.warning("⚠️  Не удалось удалить %s: %s", p, exc)


audio_processor = AudioProcessor()
