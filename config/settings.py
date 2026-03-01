"""
Настройки приложения через pydantic-settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Telegram
    BOT_TOKEN: str

    # Файлы
    MAX_FILE_SIZE_MB: int = 50
    TEMP_DIR: str = "temp"

    # Обработка
    PROCESSING_TIMEOUT: int = 120          # секунд
    MAX_ATEMPO_CHAIN: float = 2.0          # ffmpeg atempo не выше 2.0 за шаг

    # Логирование
    LOG_LEVEL: str = "INFO"

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
