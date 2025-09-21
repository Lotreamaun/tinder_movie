# Movie Tinder Bot - Техническое видение проекта

## 1. Технологии

### Backend
- **Python 3.11+** - основной язык разработки
- **FastAPI** - современный, быстрый веб-фреймворк с автоматической документацией
- **SQLAlchemy** - ORM для работы с БД
- **PostgreSQL** - основная БД для пользователей, фильмов, матчей
- **Redis** - кэширование и временное хранение сессий
- **Pydantic** - валидация данных (встроен в FastAPI)

### Frontend (Mini App)
- **React + TypeScript** - современный UI фреймворк
- **Vite** - быстрый сборщик
- **Tailwind CSS** - стилизация
- **Framer Motion** - анимации свайпов
- **Responsive design** - адаптация под мобильные устройства

### Telegram Integration
- **python-telegram-bot** - популярная библиотека для Telegram Bot API
- **Telegram Web Apps API** - для мини-приложения

### Дополнительно
- **Docker + Docker Compose** - контейнеризация для простого деплоя
- **Nginx** - reverse proxy
- **pytest** - тестирование Python кода
- **Black + isort** - форматирование кода
- **mypy** - проверка типов

## 2. Принципы разработки

### Архитектурные принципы
- **Модульность** - разделение на логические модули
- **Простота** - приоритет читаемости кода
- **DRY** - избегание дублирования кода
- **Single Responsibility** - каждый модуль отвечает за одну задачу
- **KISS** – Keep It Simple, Stupid
- **Итеративная разработка** - маленькими шагами с быстрой обратной связью

### Принципы кодирования
- **Type hints** - типизация для читаемости
- **Документирование** - docstrings для функций
- **PEP 8** - стандартный стиль Python
- **Конфигурация через переменные окружения**

### Принципы работы с данными
- **Валидация на входе** - проверка всех входящих данных
- **Транзакционность** - атомарные операции с БД
- **Кэширование** - кэш для частых запросов

### Принципы тестирования
- **Unit тесты** - только для критических функций (матчинг, валидация)
- **Мокирование** - внешних сервисов

### Принципы безопасности
- **Валидация пользовательского ввода**
- **Rate limiting** - ограничение частоты запросов
- **HTTPS only**

## 3. Структура проекта

```
tinder_movie/
├── backend/                    # Python backend
│   ├── app/                   # Основное приложение
│   │   ├── __init__.py
│   │   ├── main.py           # Точка входа FastAPI
│   │   ├── config.py         # Конфигурация
│   │   ├── database.py       # Настройка БД
│   │   ├── models/           # Модели данных
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── movie.py
│   │   │   └── match.py
│   │   ├── api/              # API endpoints
│   │   │   ├── __init__.py
│   │   │   ├── movies.py
│   │   │   ├── users.py
│   │   │   └── matches.py
│   │   ├── bot/              # Telegram bot
│   │   │   ├── __init__.py
│   │   │   ├── handlers.py
│   │   │   └── keyboards.py
│   │   ├── services/         # Бизнес-логика
│   │   │   ├── __init__.py
│   │   │   ├── movie_service.py
│   │   │   ├── matching_service.py
│   │   │   └── notification_service.py
│   │   └── migrations/       # Миграции БД
│   │       ├── __init__.py
│   │       └── versions/
│   ├── static/               # Статические файлы
│   │   ├── logs/
│   │   └── cache/
│   ├── tests/                # Тесты
│   ├── requirements.txt      # Python зависимости
│   └── Dockerfile
├── frontend/                 # React мини-приложение
│   ├── src/
│   │   ├── components/       # React компоненты
│   │   ├── hooks/           # Custom hooks
│   │   ├── services/        # API клиенты
│   │   ├── types/           # TypeScript типы
│   │   └── utils/           # Утилиты
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── docs/                     # Документация
│   ├── api/                  # API документация
│   │   ├── endpoints.md
│   │   └── schemas.md
│   └── deployment.md
├── docker-compose.yml        # Оркестрация контейнеров
├── .env.example             # Пример переменных окружения
├── .gitignore
├── README.md
├── idea.md                  # Идея проекта
└── vision.md               # Техническое видение
```

## 4. Архитектура проекта

```
┌─────────────────────────────────────────────────────────────┐
│                    Пользовательский слой                    │
├─────────────────────────────────────────────────────────────┤
│  Telegram Bot  │  Mini App (React)  │  Web Interface      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                           │
├─────────────────────────────────────────────────────────────┤
│  Telegram Web App API  │  REST API (FastAPI)  │  Polling   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Бизнес-логика                           │
├─────────────────────────────────────────────────────────────┤
│  Movie Service  │  Matching Service  │  Notification Svc  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Слой данных                             │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Redis Cache  │  Kinopoisk API            │
└─────────────────────────────────────────────────────────────┘
```

### Компоненты и их взаимодействие

**1. Telegram Bot (python-telegram-bot)**
- Обрабатывает команды пользователей
- Отправляет уведомления о матчах
- Запускает мини-приложение

**2. Mini App (React)**
- Интерфейс свайпов
- Отображение карточек фильмов
- Взаимодействие с API

**3. REST API (FastAPI)**
- `/movies` - получение списка фильмов
- `/swipe` - обработка свайпов
- `/matches` - получение матчей
- `/users` - управление пользователями

**4. Сервисы бизнес-логики:**
- **Movie Service** - работа с фильмами, кэширование
- **Matching Service** - логика матчинга пользователей
- **Notification Service** - отправка уведомлений

**5. Слой данных:**
- **PostgreSQL** - пользователи, фильмы, матчи
- **Redis** - кэш фильмов, сессии
- **Kinopoisk API** - получение информации о фильмах

## 5. Модель данных

### Основные сущности

**1. Users (Пользователи)**
```sql
users:
- id (UUID, Primary Key)
- telegram_id (BigInt, Unique)
- username (String, Nullable)
- first_name (String)
- last_active (Timestamp)
```

**2. Movies (Фильмы)**
```sql
movies:
- id (UUID, Primary Key)
- kinopoisk_id (Integer, Unique)
- title (String)
- title_original (String, Nullable)
- year (Integer)
- genre (String)
- poster_url (String)
- description (Text, Nullable)
- rating (Float, Nullable)
- created_at (Timestamp)
- is_active (Boolean)
```

**3. User_Swipes (Свайпы пользователей)**
```sql
user_swipes:
- id (UUID, Primary Key)
- user_id (UUID, Foreign Key → users.id)
- movie_id (UUID, Foreign Key → movies.id)
- swipe_type (Enum: 'like', 'dislike')
- swiped_at (Timestamp)
- group_participants (JSON) - массив telegram_id всех участников группы
- UNIQUE(user_id, movie_id, group_participants)
```

**4. Matches (Совпадения)**
```sql
matches:
- id (UUID, Primary Key)
- movie_id (UUID, Foreign Key → movies.id)
- matched_at (Timestamp)
- is_notified (Boolean)
- group_participants (JSON) - массив telegram_id ВСЕХ участников группы
- UNIQUE(movie_id, group_participants)
```

**5. User_Sessions (Сессии пользователей)**
```sql
user_sessions:
- id (UUID, Primary Key)
- user_id (UUID, Foreign Key → users.id)
- session_token (String, Unique)
- created_at (Timestamp)
- expires_at (Timestamp) - created_at + 30 дней
- is_active (Boolean)
```

### Индексы для производительности

```sql
-- Для быстрого поиска свайпов пользователя
CREATE INDEX idx_user_swipes_user_id ON user_swipes(user_id);

-- Для поиска матчей
CREATE INDEX idx_matches_group_participants ON matches USING GIN(group_participants);

-- Для поиска по Kinopoisk ID
CREATE INDEX idx_movies_kinopoisk_id ON movies(kinopoisk_id);

-- Для активных пользователей
CREATE INDEX idx_users_active ON users(last_active) WHERE last_active > NOW() - INTERVAL '1 day';
```

## 6. Сценарии работы

### Сценарий 1: Выбор партнеров для просмотра

**Пользователь:** Запускает бота
**Действия:**
1. Бот спрашивает: "С кем вы хотите посмотреть фильм?"
2. Пользователь выбирает из списка друзей или вводит до 4 никнеймов
3. Бот проверяет, есть ли эти пользователи в системе
4. Если нет - предлагает пригласить их
5. После подтверждения группы открывается мини-приложение

**API Endpoints:**
```
POST /api/groups/create
- Входные данные: { participants: [telegram_id1, telegram_id2, ...] }
- Ответ: { group_id, participants: [], session_token }

GET /api/users/search
- Параметры: ?username=@username
- Ответ: { users: [{ telegram_id, username, first_name }] }
```

### Сценарий 2: Асинхронный выбор фильмов

**Пользователи:** Все участники группы
**Действия:**
1. Каждый участник видит свои карточки фильмов независимо
2. Участник A лайкает фильм 1 → система ждет остальных
3. Участник B лайкает фильм 1 → система ждет остальных
4. Участник C лайкает фильм 1 → система ждет остальных
5. Участник D лайкает фильм 1 → **МАТЧ!** (все 4 лайкнули)
6. Система отправляет уведомления ВСЕМ участникам группы
7. Все продолжают свайпать свои карточки

**API Endpoints:**
```
GET /api/groups/{group_id}/movies/random
- Параметры: ?exclude_swiped=true
- Ответ: { movie_id, title, poster_url, year, genre }

POST /api/groups/{group_id}/vote
- Входные данные: { movie_id, vote_type: 'like'|'dislike' }
- Ответ: { success: true, match_found: boolean }

GET /api/groups/{group_id}/matches
- Ответ: { matches: [{ movie_id, movie, matched_at }] }
```

### Сценарий 3: Обнаружение матча

**Система:** Когда все участники проголосовали
**Действия:**
1. Все участники лайкнули фильм
2. Система создает матч для всей группы
3. Отправляет уведомления всем участникам
4. Показывает следующий фильм

**Логика матчинга:**
- Матч происходит ТОЛЬКО когда ВСЕ участники группы лайкнули один и тот же фильм
- Для группы из 2 человек - оба должны лайкнуть
- Для группы из 5 человек - все 5 должны лайкнуть

## 7. Деплой

### Инфраструктура

**Рекомендуемый вариант: Yandex Cloud**
- **Compute Instance:** от 200₽/месяц (1 vCPU, 1 GB RAM)
- **Managed PostgreSQL:** от 500₽/месяц
- **Load Balancer:** от 100₽/месяц
- **Итого:** ~800₽/месяц

**Альтернатива: Timeweb (дешевле)**
- **VPS:** от 100₽/месяц
- **PostgreSQL:** от 200₽/месяц
- **Итого:** ~300₽/месяц

### Стратегия разработки

**Этап 1: Локальная разработка**
```bash
# Запуск на localhost
docker-compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

**Этап 2: Деплой на Yandex Cloud**
```bash
# Создание инстанса
yc compute instance create --name tinder-movie

# Установка Docker
sudo apt update
sudo apt install docker.io docker-compose

# Клонирование и запуск
git clone <your-repo>
cd tinder_movie
docker-compose up -d
```

**Этап 3: Настройка домена и HTTPS**
- Домен .ru (99₽/год)
- SSL сертификат (бесплатно через Let's Encrypt)

### Контейнеризация

**Docker Compose для локальной разработки:**
```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/tinder_movie
    depends_on: [db, redis]
  
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - REACT_APP_API_URL=http://localhost:8000
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=tinder_movie
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes: ["postgres_data:/var/lib/postgresql/data"]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

## 8. Конфигурирование

### Структура конфигурации

**Файл `.env` (основные настройки):**
```bash
# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/tinder_movie
REDIS_URL=redis://localhost:6379

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Kinopoisk API
KINOPOISK_API_KEY=your_api_key_here

# Приложение
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=false
APP_ENV=production

# Безопасность
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here
```

**Файл `config.py` (настройки по умолчанию):**
```python
import os
from typing import Optional

class Settings:
    # База данных
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/tinder_movie")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Kinopoisk
    KINOPOISK_API_KEY: str = os.getenv("KINOPOISK_API_KEY", "")
    KINOPOISK_BASE_URL: str = os.getenv("KINOPOISK_BASE_URL", "https://kinopoiskapiunofficial.tech/api")
    
    # Приложение
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    APP_DEBUG: bool = os.getenv("APP_ENV", "development") == "development"
    
    # Безопасность
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")
    
    # Бизнес-логика
    MAX_GROUP_SIZE: int = 5
    SESSION_DURATION_HOURS: int = 24 * 30  # 30 дней
    MOVIE_CACHE_TTL: int = 3600  # 1 час

# Создаем экземпляр настроек
settings = Settings()
```

### Уровни конфигурации

1. **По умолчанию (в коде)** - безопасные значения по умолчанию
2. **Переменные окружения** - переопределяют значения по умолчанию
3. **Файл `.env`** - удобно для локальной разработки

## 9. Логгирование

### Структура логирования

**Уровни логирования:**
- **INFO** - основная информация о работе приложения
- **WARNING** - потенциальные проблемы
- **ERROR** - ошибки, требующие внимания
- **DEBUG** - подробная информация для отладки (только в development)

**Каналы логирования:**
- **Консоль** - для разработки
- **Файлы** - для production

### Настройка логирования

**Файл `logging_config.py`:**
```python
import logging
import logging.handlers
import os

def setup_logging():
    # Создаем папку для логов
    os.makedirs("logs", exist_ok=True)
    
    # Настройка форматирования
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Основной логгер
    logger = logging.getLogger('tinder_movie')
    logger.setLevel(logging.INFO)
    
    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый хендлер (ротация по дням)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        'logs/app.log',
        when='midnight',
        interval=1,
        backupCount=30  # храним 30 дней
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Отдельный файл для ошибок
    error_handler = logging.handlers.TimedRotatingFileHandler(
        'logs/errors.log',
        when='midnight',
        interval=1,
        backupCount=90  # храним 90 дней
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger
```

### Структура логов

**Файлы логов:**
```
logs/
├── app.log          # Основные логи (30 дней)
├── errors.log       # Только ошибки (90 дней)
└── user_actions.log # Действия пользователей (7 дней)
```

**Период хранения:**
- **app.log:** 30 дней
- **errors.log:** 90 дней  
- **user_actions.log:** 7 дней

**Ротация:** По времени (каждый день в полночь)

---

## Заключение

Данный документ представляет полное техническое видение проекта Movie Tinder Bot. Все решения приняты с учетом принципа KISS (Keep It Simple, Stupid) и ориентированы на пет-проект с возможностью масштабирования в будущем.

**Ключевые особенности архитектуры:**
- Асинхронный выбор фильмов для лучшего UX
- Матчинг только при совпадении ВСЕХ участников группы
- Простая и понятная структура проекта
- Готовность к масштабированию (замена polling на WebSocket)
- Минимальные затраты на инфраструктуру (~300-800₽/месяц)
