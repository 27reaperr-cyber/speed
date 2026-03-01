"""
Состояния конечного автомата (FSM) для диалога с пользователем.
"""
from aiogram.fsm.state import State, StatesGroup


class AudioState(StatesGroup):
    waiting_for_file = State()      # ожидаем аудиофайл
    waiting_for_effect = State()    # файл получен, ждём выбор эффекта
    processing = State()            # идёт обработка
