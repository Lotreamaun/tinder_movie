## 1. Модели и миграция

- [ ] 1.1 В `backend/app/models/swipe.py` добавить колонку `room_code = Column(String, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)`; заменить `UniqueConstraint("user_id", "movie_id", "group_participants", name="uq_swipe_user_movie_group")` на `UniqueConstraint("user_id", "movie_id", "room_code", name="uq_swipe_user_movie_room")`; добавить `Index("idx_user_swipes_room_code", "room_code")`.
- [ ] 1.2 Обновить докстринг `UserSwipe`: идентичность голоса даёт комната, `group_participants` — исторический снимок состава, в выборках не участвует (design.md, Decisions 1-3).
- [ ] 1.3 В `backend/app/models/match.py` добавить такую же колонку `room_code`; заменить `uq_match_movie_group` на `UniqueConstraint("movie_id", "room_code", name="uq_match_movie_room")`; убрать `Index("idx_matches_group_participants", ..., postgresql_using="gin")`, добавить `Index("idx_matches_room_code", "room_code")`; поправить комментарии в файле под новый ключ.
- [ ] 1.4 Создать миграцию `backend/app/migrations/versions/2026_09_24_HHMM_swipe_room_identity.py`: `add_column` `room_code` в `user_swipes` и `matches` (nullable, FK `rooms.id` `ondelete=SET NULL`).
- [ ] 1.5 В той же миграции — best-effort бэкфилл (design.md, Decision 6): для строк со `swiped_at`/`matched_at` за последние 24 часа выставить `room_code` там, где нормализованный (отсортированный, без дублей) `group_participants` совпадает с нормализованным `rooms.participants` ровно у **одной** комнаты; остальные строки оставить `NULL`.
- [ ] 1.6 В той же миграции — смена ключей и индексов: `drop_constraint uq_swipe_user_movie_group` → `create_unique_constraint uq_swipe_user_movie_room`; `drop_constraint uq_match_movie_group` → `create_unique_constraint uq_match_movie_room`; `create_index` по `room_code` в обеих таблицах; `drop_index idx_matches_group_participants`.
- [ ] 1.7 Написать `downgrade`: сначала дедуп (оставить самую свежую строку в каждой группе `(user_id, movie_id, group_participants)` и `(movie_id, group_participants)`), затем восстановить старые уникальные ключи и GIN-индекс, удалить новые индексы и колонки. В докстринге миграции зафиксировать, что откат теряет данные дедупа (design.md, Risks).
- [ ] 1.8 Прогнать `alembic -c ../alembic.ini upgrade head` и `downgrade -1` на локальной БД — обе стороны выполняются без ошибок.

## 2. Сессия комнаты по `room_code`

- [ ] 2.1 В `backend/app/services/room_session.py` изменить сигнатуру на `get_session_start(db, room_code)`: убрать параметр `participants` и отдельный «только для логов» `room_code`, фильтр окна заменить на `UserSwipe.room_code == room_code`.
- [ ] 2.2 Обновить докстринг модуля и функции: сессия считается по свайпам комнаты и не прерывается сменой состава участников (specs `rooms/shared-deck`, «Смена состава не прерывает сессию»).

## 3. `swipe_service` — идентичность и идемпотентность голоса

- [ ] 3.1 Удалить `SwipeService._group_contains`.
- [ ] 3.2 Переписать `get_swipe(db, user_id, movie_id, room_code)` на фильтр `UserSwipe.room_code == room_code`; `scalar_one_or_none()` теперь безопасен за счёт уникального ключа из 1.1.
- [ ] 3.3 Переписать `create_swipe` на `INSERT ... ON CONFLICT (user_id, movie_id, room_code) DO UPDATE SET swipe_type, swiped_at RETURNING *` (design.md, Decision 4): убрать ветку check-then-insert, принимать `room_code` обязательным параметром, `group_participants` писать из актуального состава комнаты.
- [ ] 3.4 Перенести валидацию размера группы на состав комнаты: `< 2` участников → `ValueError` («минимум 2 участника»), `> MAX_ROOM_SIZE` → `ValueError`; поведение сохраняется (design.md, Decision 8).
- [ ] 3.5 Переписать `check_match(db, movie_id, room_code)`: состав брать из `room.participants`, лайки — по `room_code` + `swiped_at >= session_start` (сессия из 2.1); убрать `@>`. Матч — когда число уникальных `telegram_id` лайкнувших равно числу актуальных участников комнаты.
- [ ] 3.6 Убрать из `check_match` подавление ошибки в `except Exception: return False` для случаев валидации — иначе ошибка конфигурации молча выглядит как «матча нет»; оставить логирование через `logger.error(..., exc_info=True)` и осознанное поведение при неожиданной ошибке зафиксировать в докстринге.

## 4. `match_service` — матч на пару «фильм + комната»

- [ ] 4.1 Удалить `MatchService._group_contains`.
- [ ] 4.2 Переписать `check_existing_match(db, movie_id, room_code)` на фильтр `Match.room_code == room_code`.
- [ ] 4.3 Переписать `create_match(db, movie_id, room_code)`: заполнять `room_code` и `group_participants` (актуальный состав комнаты); идемпотентность — через `check_existing_match` + уникальный ключ `uq_match_movie_room`.
- [ ] 4.4 Переписать `list_matches_for_group` в `list_matches_for_room(db, room_code, limit, offset)`.
- [ ] 4.5 Проверить, что `notification_service.send_match_notification` продолжает брать получателей из `match.group_participants` (снимок на момент матча) и правок не требует; если требует — привести к `room.participants`.

## 5. `deck_service` — исключения по комнате

- [ ] 5.1 В `_swiped_movie_ids` заменить `cast(UserSwipe.group_participants, JSONB).op("@>")(room.participants)` на `UserSwipe.room_code == room.id`; вызов `get_session_start` привести к новой сигнатуре.
- [ ] 5.2 То же в `_swiped_movie_ids_in_room`.
- [ ] 5.3 Обновить докстринги обоих методов и упоминания «группы-надмножества» в докстрингах `_replenish_deck`: свайпы других комнат больше не исключают фильмы (specs `rooms/shared-deck`, «Свайпы из другой комнаты не исключают фильм»).

## 6. API

- [ ] 6.1 В `backend/app/api/schemas.py`: в `SwipeCreate` добавить `room_code: Optional[str]`, сделать `group_participants` опциональным и помеченным как игнорируемое (обратная совместимость со старым бандлом фронта, design.md Decision 7); в `SwipeResponse` добавить `room_code`.
- [ ] 6.2 В `backend/app/api/swipes.py`: определить комнату — из `room_code` тела (проверить, что комната существует и `telegram_id` есть в `participants`, иначе 400, по образцу `api/movies.py:56-68`), иначе через `room_service.get_user_current_room` (нет активной комнаты → 400 с понятным текстом, не 500).
- [ ] 6.3 В `api/swipes.py` вызвать `check_match` **один раз** и переиспользовать результат и для `match_service.create_match`, и для поля `match_found` ответа; убрать второй вызов вместе с его `try/except: match_found = False`.
- [ ] 6.4 В `backend/app/api/matches.py`: `GET /` — заменить query-параметр `participants` на `room_code`, вызывать `list_matches_for_room`.
- [ ] 6.5 В `api/matches.py`: `GET /vote-status` — заменить `participants` на `room_code`; состав считать по `room.participants`, голоса выбирать по `UserSwipe.room_code == room_code` и `swiped_at >= session_start`, чтобы на участника приходился ровно один актуальный голос (specs `rooms/swipe-identity`, «Статус голосов по фильму…»).
- [ ] 6.6 Проверить, что 404 «комната не найдена»/400 «пользователь не в комнате» в изменённых ручках отдаются как HTTPException, а не проваливаются в `except Exception` → 500.

## 7. Фронтенд

- [ ] 7.1 В `frontend/src/services/api.ts` изменить `createSwipe`: принимать и отправлять `roomCode` вместо `groupParticipants`; обновить тип `SwipeResponse`, если в нём есть `groupParticipants`.
- [ ] 7.2 В `frontend/src/App.tsx` в `handleSwipe` передавать `roomCode: roomCodeRef.current` и заменить проверку `groupParticipants.length >= 2` на проверку наличия `roomCode` (текст ошибки для комнаты из одного участника приходит с бэкенда).
- [ ] 7.3 Прогнать `npm run lint` и `npm run build` в `frontend/` — без ошибок.

## 8. Тесты

- [ ] 8.1 Создать `backend/tests/test_swipe_identity.py`: участник свайпнул фильм, в комнату вошёл новый человек, участник свайпнул тот же фильм снова → в БД **одна** строка свайпа с актуальным типом (specs, «Участник присоединился после свайпа»).
- [ ] 8.2 Тест: лайк, затем дизлайк того же фильма в той же комнате при изменившемся составе → у участника только дизлайк, `check_match` не считает его лайкнувшим (specs, «Лайк и дизлайк одновременно невозможны»).
- [ ] 8.3 Тест: участник лайкнул фильм, затем вошёл новый человек и тоже лайкнул → матч создаётся, ранний лайк засчитан (specs, «Новый участник достраивает матч»); а пока новый участник не проголосовал — матч не создаётся.
- [ ] 8.4 Тест идемпотентности матча: повторная проверка после смены состава не создаёт вторую запись в `matches` и не шлёт второго уведомления (замокать `notification_service`).
- [ ] 8.5 Тест гонки (по образцу `test_shared_deck.py`): два параллельных одинаковых свайпа → одна строка, оба запроса успешны, ни одного `IntegrityError`/500.
- [ ] 8.6 Тест изоляции комнат: те же участники в двух комнатах, свайп в одной → в другой фильм не исключён из показа, голос не учтён (specs, «Свайпы другой комнаты не смешиваются» и `rooms/shared-deck`, «Свайпы из другой комнаты не исключают фильм»).
- [ ] 8.7 Тест сессии: свайпы комнаты с разрывом менее 24ч при изменившемся составе → сессия продолжается, ранние свайпы учтены; с разрывом ≥24ч → голоса прошлой сессии не учитываются ни как исключения, ни при проверке матча.
- [ ] 8.8 Тест API: `POST /api/swipes/` без активной комнаты и с `room_code` чужой комнаты → 400 (не 500); свайп с корректным `room_code` → `room_code` в БД непустой.
- [ ] 8.9 Обновить `backend/tests/test_shared_deck.py` под новую сигнатуру `get_session_start` и `create_swipe`; прогнать `pytest` в `backend/` — все тесты зелёные.

## 9. Верификация

- [ ] 9.1 Ручная проверка на локальном стенде: комната из двух участников, свайпы, затем вход третьего участника в середине сессии → у участников не появляется повторных карточек по уже свайпнутым фильмам, свайп того же фильма обновляет голос, ложного матча нет.
- [ ] 9.2 Ручная проверка матча: двое лайкнули фильм, третий вошёл и лайкнул его же → один матч, одно уведомление на участника.
- [ ] 9.3 Проверить по логам/БД, что у всех новых строк `user_swipes` и `matches` заполнен `room_code`.
