## 1. Надёжность backend (базовый слой)

- [ ] 1.1 Починить форматтер логов в `backend/app/logging_config.py` (убрать конкатенацию строк-литералов), проверить вывод
- [ ] 1.2 Убрать дублирующие вызовы `check_match` в `backend/app/api/swipes.py` (одна проверка на свайп, результат в ответе)
- [ ] 1.3 `leave_room`: выход последнего участника возвращает штатный результат (комната удалена) вместо `ValueError` в `backend/app/services/room_service.py` и бот-хендлере
- [ ] 1.4 Вынести загрузку фильмов из Kinopoisk из пути запроса: `get_random_movie` перестаёт вызывать внешний API
- [ ] 1.5 Добавить фоновый цикл наполнения/ротации фильмов (порог, батч, backoff при 429) с запуском при старте API
- [ ] 1.6 Обработка пустой базы: запрос случайного фильма возвращает 404 без блокировки

## 2. Надёжные уведомления (outbox)

- [ ] 2.1 Миграция: таблица `match_notifications` (match_id, status, attempts, next_attempt_at, error)
- [ ] 2.2 При создании матча писать строку outbox вместо спавна потока; удалить thread+event loop из `notification_service.py`
- [ ] 2.3 Воркер в процессе бота: забирает pending, отправляет через Telegram Bot API, на успехе — sent + `match.is_notified=true`
- [ ] 2.4 Ретраи с backoff: failed → attempts+1, `next_attempt_at`, лог ошибки

## 3. Аутентификация через Telegram initData

- [ ] 3.1 Модуль валидации initData (HMAC-SHA256, constant-time сравнение, проверка `auth_date` и `user.id`)
- [ ] 3.2 FastAPI-зависимость `get_current_user` из заголовка `X-Telegram-Init-Data`
- [ ] 3.3 Перевести эндпоинты swipes/rooms/matches с заголовка `telegram-id` на проверенную личность; удалить клиентский `telegram-id` из контракта
- [ ] 3.4 Убрать мёртвые `SECRET_KEY`/`JWT_SECRET` из конфига

## 4. Конфигурация и rate limiting

- [ ] 4.1 Переписать `app/config.py` на строгие pydantic-настройки: обязательные переменные проверяются при старте, нет секретов-заглушек
- [ ] 4.2 Подключить rate limiting (slowapi, лимит на identity+IP), ответ 429 с Retry-After

## 5. Контейнеризация и деплой

- [ ] 5.1 `backend/Dockerfile` (мультистейдж, non-root, entrypoint: alembic upgrade head + uvicorn)
- [ ] 5.2 `frontend/Dockerfile` (node build → nginx, proxy `/api` на backend)
- [ ] 5.3 `.dockerignore` для backend и frontend
- [ ] 5.4 `docker-compose.yml`: db (postgres, healthcheck, volume), api (depends_on db healthy), bot (single replica), frontend
- [ ] 5.5 Проверить: `docker compose up` поднимает стек, `GET /health` отвечает 200, миграции применяются до старта API

## 6. CI/CD

- [ ] 6.1 Workflow GitHub Actions: lint (ruff) + pytest для backend, build (tsc) + eslint для frontend
- [ ] 6.2 Шаг сборки обоих Docker-образов; публикация в registry по ветке/тегу
- [ ] 6.3 Секреты (TELEGRAM_BOT_TOKEN, KINOPOISK_API_KEY, registry) — через GitHub secrets, не в репозитории

## 7. Фронтенд: передача initData

- [ ] 7.1 `api.ts`: заголовок `X-Telegram-Init-Data` из `window.Telegram.WebApp.initData` вместо ручного `telegram-id`
- [ ] 7.2 Dev-фоллбэк (VITE_DEV_TELEGRAM_ID) только под `import.meta.env.DEV`; в проде без initData — 401
- [ ] 7.3 Обработка 401/429 на фронте с понятным сообщением

## 8. Тесты

- [ ] 8.1 pytest: валидация initData (валидный, подменённый, истёкший)
- [ ] 8.2 pytest: свайп-матчинг — проверка вызывается один раз; match создаётся идемпотентно (mock Kinopoisk)
- [ ] 8.3 pytest: outbox — успешная отправка ставит sent/is_notified, ошибка → retry
- [ ] 8.4 pytest: leave_room для последнего участника — штатный результат
- [ ] 8.5 Линт/формат: ruff по backend без ошибок
