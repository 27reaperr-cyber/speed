"""
Middleware для ограничения частоты запросов (throttling).
"""
import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Ограничивает частоту обработки сообщений одного пользователя.
    rate_limit — минимальный интервал (в секундах) между сообщениями.
    """

    def __init__(self, rate_limit: float = 2.0) -> None:
        self.rate_limit = rate_limit
        self._last_message: dict[int, float] = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id if event.from_user else 0
        now = time.monotonic()
        last = self._last_message[user_id]

        if now - last < self.rate_limit:
            remaining = self.rate_limit - (now - last)
            logger.debug("🛑 Throttle: user=%d, wait=%.1fs", user_id, remaining)
            await event.answer(
                f"⏳ Не так быстро! Подожди {remaining:.1f} сек."
            )
            return None

        self._last_message[user_id] = now
        return await handler(event, data)
