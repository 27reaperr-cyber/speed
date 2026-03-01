# 🎧 Speed Up & Slowed Bot

Telegram-бот для обработки аудиофайлов: ускорение, замедление и изменение тональности.

## 📁 Структура проекта

```
speedbot/
├── bot.py                    # точка входа, запуск polling
├── config/
│   ├── __init__.py
│   └── settings.py           # настройки через pydantic-settings + .env
├── handlers/
│   ├── __init__.py
│   ├── start.py              # /start, /help
│   ├── audio.py              # приём файлов, обработка, отправка
│   └── errors.py             # глобальный обработчик ошибок
├── middlewares/
│   ├── __init__.py
│   └── throttle.py           # ограничение частоты запросов
├── services/
│   ├── __init__.py
│   └── audio_service.py      # ffmpeg-обработка, реестр эффектов
├── utils/
│   ├── __init__.py
│   ├── keyboards.py          # фабрика inline-клавиатур
│   └── states.py             # FSM-состояния
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## ⚙️ Установка (локально)

### 1. Зависимости системы

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install ffmpeg python3.11 python3.11-venv

# macOS (Homebrew)
brew install ffmpeg python@3.11
```

### 2. Python-окружение

```bash
cd speedbot
python3.11 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Конфигурация

```bash
cp .env.example .env
# Открой .env и вставь токен бота (получи у @BotFather)
```

### 4. Запуск

```bash
python bot.py
```

## 🐳 Docker

```bash
cp .env.example .env
# Заполни BOT_TOKEN в .env

docker-compose up -d
docker-compose logs -f          # просмотр логов
```

## 🎛 Доступные эффекты

| Эффект | Описание | ffmpeg-фильтр |
|--------|----------|---------------|
| 🚀 Speed Up ×1.25 | Ускорение, питч сохранён | `atempo=1.25` |
| 🚀 Speed Up ×1.5  | Ускорение, питч сохранён | `atempo=1.5` |
| 🚀 Speed Up ×2.0  | Ускорение, питч сохранён | `atempo=2.0` |
| 🐌 Slowed ×0.75   | Замедление, питч сохранён | `atempo=0.75` |
| 🐌 Slowed ×0.5    | Замедление, питч сохранён | `atempo=0.5` |
| 🎵 Pitch +2       | Тон выше на 2 полутона | `asetrate+atempo` |
| 🎵 Pitch +4       | Тон выше на 4 полутона | `asetrate+atempo` |
| 🎵 Pitch -2       | Тон ниже на 2 полутона | `asetrate+atempo` |
| 🎵 Pitch -4       | Тон ниже на 4 полутона | `asetrate+atempo` |

## 🔧 Технические детали

- **aiogram 3.x** — асинхронный фреймворк с FSM
- **ffmpeg atempo** — изменение скорости без артефактов тональности
- **asetrate + atempo** — сдвиг тональности с компенсацией темпа
- **UUID-имена** — все временные файлы получают уникальные имена
- **auto-cleanup** — файлы удаляются в блоке `finally` после отправки
- **Throttling** — антиспам: интервал 3 сек между запросами
- **Timeout** — обработка прерывается через 120 сек
- **Лимит файла** — 50 МБ (ограничение Telegram Bot API)
