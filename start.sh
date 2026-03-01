#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  start.sh — стартовый скрипт для BotHost.ru и других хостингов
#  Используй этот файл как точку входа вместо python bot.py,
#  если хостинг поддерживает shell-скрипты.
# ─────────────────────────────────────────────────────────────

set -e  # Прерываем выполнение при любой ошибке

echo "========================================"
echo "  Speed Up & Slowed Bot — старт"
echo "========================================"

# ── 1. Установка ffmpeg ───────────────────────────────────────
if command -v ffmpeg &>/dev/null; then
    echo "[ffmpeg] ✅ Уже установлен: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "[ffmpeg] ⚙️  Не найден — устанавливаю..."
    apt-get update -y
    apt-get install -y --no-install-recommends ffmpeg
    echo "[ffmpeg] ✅ Установлен: $(ffmpeg -version 2>&1 | head -1)"
fi

# ── 2. Создание временной директории ─────────────────────────
mkdir -p temp
echo "[temp] ✅ Директория temp готова"

# ── 3. Установка Python-зависимостей (на случай первого запуска) ──
if [ -f requirements.txt ]; then
    echo "[pip] ⚙️  Устанавливаю зависимости..."
    pip install -q --no-cache-dir -r requirements.txt
    echo "[pip] ✅ Зависимости установлены"
fi

# ── 4. Запуск бота ────────────────────────────────────────────
echo "[bot] 🚀 Запускаю bot.py..."
python bot.py
