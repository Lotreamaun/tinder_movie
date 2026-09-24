# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Movie Tinder Bot: Telegram-бот (комнаты) + React-мини-приложение (свайпы). Матч создаётся, когда **все** участники комнаты (до 5) лайкнули один фильм. Документация и комментарии в проекте — на русском; пишите так же. Общий обзор — в [README.md](README.md), техническое видение — в [doc/vision.md](doc/vision.md).

## Команды

Backend (из `backend/`, venv в корне `.venv`, нужен PostgreSQL и `.env` в корне):

```
uvicorn app.main:app --reload        # API на :8000
python3 -m app.run_bot               # Telegram-бот отдельным процессом (polling)
alembic -c ../alembic.ini upgrade head   # миграции (alembic.ini лежит в корне репо)
pytest                               # все тесты
pytest tests/test_shared_deck.py::test_name   # один тест
```

Тесты идут против реальной PostgreSQL: `TEST_DATABASE_URL` (по умолчанию `postgresql://lotreamaun@localhost:5432/tinder_movie_test`; БД нужно создать заранее). `conftest.py` накатывает настоящие Alembic-миграции и подменяет `DATABASE_URL` до импорта `app`, а `TELEGRAM_BOT_TOKEN` обнуляет.

Frontend (из `frontend/`): `npm run dev`, `npm run build` (`tsc -b && vite build`), `npm run lint`. Vite проксирует `/api/*` на `localhost:8000`; `VITE_API_BASE_URL` — в `frontend/.env`. Для Telegram Mini App локально нужен `ngrok`.

## Архитектура

Слои backend (`backend/app/`): `api/` (тонкие FastAPI-роуты, ответы в обёртке `ApiResponse[T]`) → `services/` (вся бизнес-логика, сервисы — синглтоны, их вызывают и API, и бот) → `models/` (SQLAlchemy 2.0). `config.py` читает `.env` через `os.getenv` в класс `Settings` на этапе импорта — поэтому переменные окружения надо выставлять до импорта `app`.

Ключевое, что не видно из одного файла:

- **Общий колод комнаты** ([deck_service.py](backend/app/services/deck_service.py)): у комнаты один упорядоченный список фильмов (`room_decks.movie_ids`), у каждого участника — свой курсор (`room_deck_positions`). Каждый запрос «следующего фильма» продвигает курсор под `FOR UPDATE`, поэтому параллельная предзагрузка фронта не даёт дублей, а последовательность одинакова для всех — иначе матч был бы недостижим. Алгоритм: prune → clamp → scan → advance; одна транзакция, финальный `commit`. Есть тест на гонки — `tests/test_shared_deck.py`.
- **Матч** — `swipe_service.check_match` смотрит, лайкнули ли фильм все `participants` комнаты; `match_service` создаёт матч идемпотентно, `notification_service` шлёт уведомления в Telegram в фоновом потоке со своим asyncio-loop.
- **Комнаты** идентифицируются 6-символьным кодом (PK), участники — JSON-массив `telegram_id`. Бот (`bot/handlers.py`) управляет комнатами, веб-приложение — только свайпами.
- **Фильмы** подгружаются из Kinopoisk API автоматически при падении числа ниже порога, старые ротируются (пороги — в `Settings`).
- **Frontend**: `App.tsx` держит очередь и предзагружает фильмы, `components/MovieCard.tsx` — свайп-жесты (framer-motion / react-swipeable; реагирует только на горизонтальный свайп), `services/api.ts` — Axios с автоконвертацией `snake_case` ↔ `camelCase`.

README местами устарел (нет `room_decks`/`room_deck_positions`, «tests пока пусто») — ориентируйтесь на код.

## Процесс и конвенции

- Изменения ведутся через **OpenSpec** (`openspec/`, спецификации в `openspec/specs/`, активные изменения в `openspec/changes/`; команды `opsx-*` в `.cursor/`, `.github/`, `.gemini/`, `.opencode/`). Завершённые изменения архивируются с синком дельта-спеков.
- `.cursor/rules/`: KISS, один модуль — одна задача, type hints и docstrings на публичных функциях, Black + isort, валидация входа через Pydantic, логирование через `logger.error(..., exc_info=True)`. Правило workflow: сначала план, потом реализация; после задачи предлагать коммит.
- Коммиты — Conventional Commits на русском (`fix(backend): …`, `chore(openspec): …`).
- Схема БД меняется только через новую Alembic-миграцию в `backend/app/migrations/versions/` (имя `YYYY_MM_DD_HHMM_описание.py`).
