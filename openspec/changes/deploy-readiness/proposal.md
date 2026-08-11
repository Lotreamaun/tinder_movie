## Why

Продукт нельзя задеплоить в текущем состоянии: API полностью открыто (идентификация подделывается обычным заголовком `telegram-id`), нет Docker/CI/CD, миграции не выполняются при развёртывании, а в коде есть блокирующие баги (поломанный формат логов, тройной запрос в БД на свайп, потеря уведомлений о матчах). Это первый шаг к боевому запуску.

## What Changes

- **Безопасность**: валидация Telegram WebApp `initData` (HMAC-SHA256 по токену бота) на бэкенде; идентификация пользователя по проверенной подписи, а не по доверенному заголовку `telegram-id`. Rate limiting на API. CORS — список разрешённых origin'ов.
- **Инфраструктура**: `Dockerfile` (backend и frontend/nginx), `docker-compose` (postgres + api + bot + frontend), `.dockerignore`, entrypoint с `alembic upgrade head` перед стартом API. GitHub Actions: lint + тесты + сборка образов.
- **Деплой бота**: webhook вместо polling (или гарантия единственного инстанса бота) — исключить дубли уведомлений.
- **Баги бэкенда**: починить форматтер логов (`logging_config.py`), убрать троекратный вызов `check_match` в `create_swipe`, отправлять уведомления надёжно (retry, `is_notified` по фактическому результату, а не сразу), корректный исход `leave_room` для последнего участника, вынести загрузку/ротацию фильмов из Kinopoisk из пути запроса, асинхронный доступ к БД.
- **Тесты**: pytest для критической логики (матчинг, свайпы, комнаты) с моком Kinopoisk API.
- **Конфигурация**: убрать секреты-заглушки по умолчанию, строгие валидации настроек, секреты только из окружения.

## Capabilities

### New Capabilities

- `identity/telegram-auth`: проверка подлинности пользователя через подписанный Telegram WebApp initData; API доверяет только подтверждённой личности, заголовок-телеграм-id перестаёт быть способом идентификации.
- `platform/deployment`: контейнеризация, docker-compose, автоматические миграции при старте, CI/CD pipeline, безопасная доставка секретов.
- `platform/reliability`: надёжная фоновая отправка уведомлений о матчах с ретраями, устранение дублирующих запросов и блокирующих вызовов внешних API в пути HTTP-запроса, корректная работа с событиями жизни комнаты.

### Modified Capabilities

_(нет — существующих спеков в `openspec/specs/` нет)_

## Impact

- **Backend**: `app/api/*` (эндпоинты свайпов/комнат получают проверенную личность), `app/config.py` (строгие настройки), `app/database.py` (async-движок), `app/services/movie_service.py`, `app/services/match_service.py`, `app/services/notification_service.py`, `app/logging_config.py`, `app/bot/*` (webhook).
- **Frontend**: отправка `initData` вместо ручного `telegram-id`; обработка 401/429.
- **Инфраструктура**: новые файлы `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/*`.
- **Зависимости**: добавление slowapi/Redis-опции для rate limit, asyncpg, uvicorn-worker/nginx; pytest в dev-зависимости.
