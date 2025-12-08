# 🚀 Docker развертывание Movie Tinder Bot

## ✅ ИСПРАВЛЕНИЯ (2025-12-07)

**Устранены критические проблемы:**
- ❌ Удалены конфликтующие Vercel файлы (`vercel.json`, `api/index.py`, `mangum`)
- ✅ Восстановлена правильная nginx архитектура (backend + frontend + nginx)
- ✅ Исправлены API пути (убран двойной `/api/`)
- ✅ Настроено проксирование через nginx

## 🏗️ Архитектура

- **Backend (Python/FastAPI)**: API сервер + Telegram бот в отдельных контейнерах
- **Frontend (React)**: Production build, обслуживается через Nginx
- **Nginx**: Reverse proxy, обслуживает frontend + проксирует `/api` на backend
- **База данных**: Supabase (PostgreSQL)
- **Redis**: Пока не используется в MVP

## 📋 Предварительные требования

- ✅ Docker и Docker Compose
- ✅ Telegram Bot Token (получить у @BotFather)
- ✅ Kinopoisk API Key (получить на kinopoiskapiunofficial.tech)
- ✅ Supabase база данных настроена и заполнена

## ⚙️ Настройка переменных окружения

1. Скопируйте пример файла переменных:
```bash
cp env.example .env
```

2. Отредактируйте `.env` файл:
```bash
# База данных Supabase
DATABASE_URL=postgresql://user:password@your-supabase-host:5432/tinder_movie

# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_actual_bot_token

# Kinopoisk API Key
KINOPOISK_API_KEY=your_actual_api_key

# Секреты (придумайте свои)
SECRET_KEY=your_random_secret_key
JWT_SECRET=your_random_jwt_secret
```

## 🚀 Запуск

```bash
# Собрать и запустить все сервисы
docker-compose up --build

# Или в фоне
docker-compose up --build -d
```

## 📊 Сервисы

После запуска будут доступны:

- **Frontend**: http://localhost
- **API Health**: http://localhost/health
- **API Docs**: http://localhost/docs (через nginx прокси)

## 🔍 Проверка работы

```bash
# Проверить статус сервисов
docker-compose ps

# Посмотреть логи
docker-compose logs backend
docker-compose logs bot
docker-compose logs frontend
docker-compose logs nginx

# Проверить API
curl http://localhost/health
curl http://localhost/api/movies/random
```

## 🛠️ Управление

```bash
# Остановить все сервисы
docker-compose down

# Пересобрать и перезапустить
docker-compose up --build --force-recreate

# Очистить volumes (если нужно)
docker-compose down -v
```

## 📁 Структура файлов

```
├── docker-compose.yml    # Основная конфигурация Docker
├── backend/
│   ├── Dockerfile       # Backend контейнер
│   └── requirements.txt # Python зависимости
├── frontend/
│   └── Dockerfile       # Frontend контейнер
├── nginx/
│   └── nginx.conf       # Nginx конфигурация
└── .env                 # Переменные окружения
```

## 🔒 Безопасность

- Backend API доступен только через Nginx (не пробрасывается наружу)
- Все API запросы идут через `/api/` прокси
- Секреты хранятся в переменных окружения Docker
- Nginx настроен с правильными заголовками безопасности

## 🐛 Отладка

### Логи контейнеров
```bash
# Логи всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f backend
```

### Вход в контейнер
```bash
# Войти в backend контейнер
docker-compose exec backend bash

# Проверить переменные окружения
docker-compose exec backend env
```

### Ошибки подключения
- Проверьте что Supabase база доступна
- Проверьте TELEGRAM_BOT_TOKEN
- Проверьте KINOPOISK_API_KEY

## 🩺 Тестирование после запуска

### 1. Проверить статус контейнеров:
```bash
docker-compose ps
```

### 2. Проверить логи:
```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f nginx
```

### 3. Тестирование API через curl:
```bash
# Health check
curl http://localhost/health

# Swagger UI (должен открыться браузер)
curl -I http://localhost/api/docs

# Получить случайный фильм
curl http://localhost/api/movies/random

# Создать пользователя
curl -X POST http://localhost/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123456789, "first_name": "TestUser"}'
```

### 4. Проверка frontend:
Открыть http://localhost в браузере

## 🎯 Production готовность

Конфигурация оптимизирована для production:
- ✅ Multi-stage builds для уменьшения размера образов
- ✅ Nginx для статических файлов с кэшированием
- ✅ Отдельные сервисы для API и бота
- ✅ Переменные окружения для секретов
- ✅ Health checks и graceful shutdown