# Movie Tinder Bot

Telegram бот для совместного выбора фильмов в группе друзей.

## Описание

Movie Tinder Bot позволяет группе друзей асинхронно выбирать фильмы для совместного просмотра. Каждый участник группы независимо свайпает карточки фильмов, а система находит совпадения когда ВСЕ участники группы лайкнули один и тот же фильм.

## Технологии

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Bot:** python-telegram-bot
- **Деплой:** Docker, Docker Compose

## Быстрый старт

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd tinder_movie
```

### 2. Настройка окружения
```bash
# Копируем файл с переменными окружения
cp env.example .env

# Редактируем .env файл с вашими настройками
nano .env
```

### 3. Установка зависимостей
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 4. Запуск приложения
```bash
# Запуск backend
cd backend
python -m app.main
```

## Структура проекта

```
tinder_movie/
├── backend/                    # Python backend
│   ├── app/                   # Основное приложение
│   │   ├── models/           # Модели данных
│   │   ├── api/              # API endpoints
│   │   ├── bot/              # Telegram bot
│   │   ├── services/         # Бизнес-логика
│   │   └── migrations/       # Миграции БД
│   └── requirements.txt      # Python зависимости
├── frontend/                 # React мини-приложение
├── docs/                     # Документация
└── docker-compose.yml        # Оркестрация контейнеров
```

## Разработка

Проект разрабатывается итеративно согласно плану в `tasklist.md`. Каждая итерация добавляет минимальный, но работающий функционал.

### Текущий статус
- **Итерация 1:** Настройка проекта ✅
- **Итерация 2:** Базовая структура FastAPI ⏳

## Лицензия

MIT License
