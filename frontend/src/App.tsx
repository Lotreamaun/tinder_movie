import { useState, useEffect, useRef, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import { MovieCard, type ExitDirection } from './components/MovieCard';
import { SkeletonCard } from './components/SkeletonCard';
import { MatchOverlay } from './components/MatchOverlay';
import { getRandomMovie, createSwipe, getMyRoom, ApiError } from './services/api';
import { getTelegramUserId, disableVerticalSwipes } from './utils/telegram';
import { preloadImage } from './utils/image';
import './App.css';
import type { Movie } from './types/movie_types';

// Сколько фильмов набираем в очередь при старте
const PRELOAD_COUNT = 5;

function App() {
  // 1. Текущий фильм
  const [currentMovie, setCurrentMovie] = useState<Movie | null>(null);

  // 2. Очередь фильмов (предзагрузка)
  const [_movieQueue, setMovieQueue] = useState<Movie[]>([]);

  // 3. Состояние загрузки
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 3b. Догрузка следующего фильма при исчерпании очереди (показывается SkeletonCard)
  const [isLoadingNext, setIsLoadingNext] = useState<boolean>(false);

  // 4. Неблокирующий баннер ошибки
  const [error, setError] = useState<string | null>(null);

  // 5. Telegram ID
  const [telegramId, setTelegramId] = useState<number | null>(null);

  // 5b. Готова ли инициализация Telegram WebApp SDK (баннер «Telegram ID not set»
  //     показываем только после этого, чтобы не мигал во время инициализации).
  const [sdkInitDone, setSdkInitDone] = useState<boolean>(false);

  // 6. Участники комнаты (для групповых свайпов)
  const [groupParticipants, setGroupParticipants] = useState<number[]>([]);

  // 7. Код текущей комнаты (для общего колода фильмов)
  const [roomCode, setRoomCode] = useState<string | null>(null);

  // 8. Направление последнего свайпа (для exit-анимации вылета карточки)
  const [exitDirection, setExitDirection] = useState<ExitDirection | null>(null);

  // 9. Мэтч — фильм, по которому найден матч
  const [matchedMovie, setMatchedMovie] = useState<Movie | null>(null);

  // 10. Монотонный счётчик показов — ключ MovieCard. С key={movie.id} повтор
  //     фильма подряд не перемонтировал карточку: exit-анимация не играла и
  //     нажатие визуально пропадало.
  const [cardSeq, setCardSeq] = useState<number>(0);

  // Ref-копии — чтобы обработчики видели актуальные значения без пересоздания
  const movieQueueRef = useRef<Movie[]>(_movieQueue);
  const currentMovieRef = useRef<Movie | null>(currentMovie);
  const telegramIdRef = useRef<number | null>(telegramId);
  const roomCodeRef = useRef<string | null>(roomCode);

  useEffect(() => { movieQueueRef.current = _movieQueue; }, [_movieQueue]);
  useEffect(() => { currentMovieRef.current = currentMovie; }, [currentMovie]);
  useEffect(() => { telegramIdRef.current = telegramId; }, [telegramId]);
  useEffect(() => { roomCodeRef.current = roomCode; }, [roomCode]);

  // Догрузка следующего фильма (из общего колода комнаты, если она есть) + preload постера.
  const loadMoreMovies = useCallback(async (): Promise<Movie> => {
    const movie = await getRandomMovie({
      roomCode: roomCodeRef.current ?? undefined,
      telegramId: telegramIdRef.current ?? undefined,
    });
    preloadImage(movie.posterUrl);
    return movie;
  }, []);

  // Пополнение очереди с дедупом по `id`: фильм, уже лежащий в очереди или
  // показанный сейчас, в неё не добавляется — повтор не должен тратить нажатие.
  const enqueueUnique = useCallback((movie: Movie) => {
    setMovieQueue((queue) =>
      queue.some((m) => m.id === movie.id) || currentMovieRef.current?.id === movie.id
        ? queue
        : [...queue, movie]
    );
  }, []);

  // Загружаем первый фильм и telegramId при монтировании компонента
  useEffect(() => {
    // Флаг отмены запуска: cleanup эффекта помечает запуск отменённым.
    // Нужен из-за двойного монтирования в StrictMode (dev): без него
    // initializeApp отрабатывал дважды, и выброшенный набор очереди
    // безвозвратно продвигал курсор участника по колоду комнаты
    // (позиция двигается при выдаче фильма, а не при свайпе).
    let cancelled = false;

    const initializeApp = async () => {
      try {
        // Блокируем вертикальные свайпы (сворачивание mini-app) — без этого
        // горизонтальные свайпы карточки дёргают всё окно приложения.
        disableVerticalSwipes();

        // 1. Ждём инициализацию Telegram WebApp SDK (короткий retry/таймаут),
        //    чтобы не показывать заглушку «Telegram ID not set» раньше времени.
        const tgUserId = await getTelegramUserId();
        if (cancelled) return;
        setSdkInitDone(true);

        let resolvedId: number | null = null;
        if (tgUserId) {
          resolvedId = tgUserId;
          setTelegramId(tgUserId);
          console.log('Telegram ID from WebApp:', tgUserId);
        } else {
          // Фоллбэк: localStorage (для тестов в браузере)
          const storedTelegramId = localStorage.getItem('telegramId');
          if (storedTelegramId) {
            const parsed = Number(storedTelegramId);
            if (!Number.isNaN(parsed)) {
              resolvedId = parsed;
              setTelegramId(parsed);
              console.log('Telegram ID from localStorage:', storedTelegramId);
            }
          } else {
            // Dev fallback: .env (только локальная разработка)
            const devId = import.meta.env.VITE_DEV_TELEGRAM_ID;
            if (import.meta.env.DEV && devId) {
              const parsed = Number(devId);
              if (!Number.isNaN(parsed)) {
                resolvedId = parsed;
                setTelegramId(parsed);
                console.warn('Using VITE_DEV_TELEGRAM_ID from .env:', parsed);
              }
            }
          }
        }

        // 2. Загружаем комнату пользователя (нужно для групповых свайпов)
        let currentRoomCode: string | null = null;
        if (resolvedId) {
          const room = await getMyRoom(resolvedId);
          if (cancelled) return;
          if (room && room.participantIds) {
            setGroupParticipants(room.participantIds);
            currentRoomCode = room.roomCode ?? null;
            setRoomCode(currentRoomCode);
            console.log('Room participants:', room.participantIds);
            console.log('Room code:', currentRoomCode);
          } else {
            console.warn('User is not in any room — swipes require 2+ participants');
          }
        }

        if (cancelled) return;

        setError(null);
        setIsLoading(true);

        // 3. Набираем начальную очередь фильмов (из общего колода комнаты, если она есть).
        //    Последовательно, а не через Promise.all: сетевой слой WebKit (Telegram на
        //    iPhone/macOS) склеивает одинаковые одновременные XHR-GET в один запрос и
        //    раздаёт всем вызовам одно тело ответа — очередь набиралась копиями одного
        //    фильма. Выигрыша от параллелизма всё равно нет: бэкенд сериализует запросы
        //    участника на `FOR UPDATE` строки колоды.
        const roomParams = currentRoomCode && resolvedId
          ? { roomCode: currentRoomCode, telegramId: resolvedId }
          : undefined;
        const movies: Movie[] = [];
        for (let i = 0; i < PRELOAD_COUNT; i++) {
          const movie = await getRandomMovie(roomParams);
          if (cancelled) return;
          // Дедуп по `id` — повтор в очередь не попадает
          if (movies.some((m) => m.id === movie.id)) continue;
          movies.push(movie);
          preloadImage(movie.posterUrl);
        }

        setMovieQueue(movies.slice(1));
        setCurrentMovie(movies[0] ?? null);
        if (import.meta.env.DEV) {
          console.log('movie (first fetched):', movies[0]);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to initialize app:', err);
        setError(err instanceof ApiError ? err.message : 'Failed to initialize app');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    initializeApp();

    return () => {
      cancelled = true;
    };
  }, []);

  // Обработка свайпа: карточка уходит сразу (оптимистично), отправка — в фоне.
  const handleSwipe = useCallback((swipeType: 'like' | 'dislike') => {
    const movie = currentMovieRef.current;
    if (!movie) return;

    // Направление для exit-анимации вылета
    setExitDirection(swipeType === 'like' ? 'right' : 'left');

    // Новый ключ карточки: смена происходит на каждом засчитанном свайпе,
    // даже если следующий фильм совпал с текущим по `id`
    setCardSeq((n) => n + 1);

    // Сразу показываем следующий фильм из очереди
    const queue = movieQueueRef.current;
    const [next, ...rest] = queue;
    if (next) {
      setCurrentMovie(next);
      setMovieQueue(rest);
      preloadImage(next.posterUrl);
      // Дополняем очередь, если осталось мало
      if (rest.length < 3) {
        loadMoreMovies()
          .then(enqueueUnique)
          .catch((err) => console.error('Failed to prefetch next movie:', err));
      }
    } else {
      // Очередь пуста: показываем скелетон и догружаем следующий фильм.
      // Заглушка «Нет доступных фильмов» появится только если догрузка вернула пусто/ошибку.
      setIsLoadingNext(true);
      setCurrentMovie(null);
      loadMoreMovies()
        .then((m) => setCurrentMovie(m))
        .catch((err) => {
          console.error('Failed to load next movie:', err);
          setError('Не удалось загрузить следующий фильм. Проверьте соединение.');
        })
        .finally(() => setIsLoadingNext(false));
    }

    // Отправка свайпа — в фоне, UI не блокируется
    const tgId = telegramIdRef.current;
    if (tgId && groupParticipants.length >= 2) {
      createSwipe({
        movieId: movie.id,
        swipeType,
        groupParticipants,
        telegramId: tgId,
      })
        .then((swipeResult) => {
          // Проверяем, найден ли мэтч
          if (swipeResult?.matchFound) {
            setMatchedMovie(movie);
          }
        })
        .catch((err) => {
          console.error('Failed to create swipe:', err);
          setError(
            err instanceof ApiError
              ? `Не удалось отправить свайп: ${err.message}`
              : 'Не удалось отправить свайп. Проверьте соединение.'
          );
        });
    } else if (tgId) {
      setError('Нужно минимум 2 участника в комнате для свайпов');
    }
  }, [groupParticipants, loadMoreMovies, enqueueUnique]);

  return (
    <div className="min-h-screen flex-1 flex flex-col bg-background text-foreground">
      {/* Dev/UX Banner when telegramId is missing — только после инициализации SDK */}
      {sdkInitDone && !telegramId && (
        <div className="mb-4 rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-yellow-800">
          <div className="mb-2 font-semibold">Telegram ID not set.</div>
          <div className="text-sm">
            Swipes are disabled. Set localStorage key <code>telegramId</code> or use env <code>VITE_DEV_TELEGRAM_ID</code> in dev.
          </div>
          {import.meta.env.DEV && (
            <div className="mt-3">
              <DevTelegramIdSetter onSet={(id) => setTelegramId(id)} />
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
          <div className="flex items-center justify-between">
            <div className="font-semibold">Ошибка</div>
            <button
              onClick={() => setError(null)}
              aria-label="Закрыть сообщение об ошибке"
              className="text-lg leading-none text-red-400 hover:text-red-700"
            >
              ×
            </button>
          </div>
          <div className="text-sm">{error}</div>
        </div>
      )}

      {/* Свайп-область на весь экран: небольшие отступы по бокам/снизу,
          сверху — safe-area (dynamic island на iPhone) */}
      <div className="relative flex-1">
        <div
          className="movie-container absolute inset-0 mx-auto max-w-[480px]"
          style={{
            paddingLeft: 12,
            paddingRight: 12,
            paddingTop: 'calc(max(var(--tg-content-safe-area-inset-top, 0px), env(safe-area-inset-top, 0px)) + 12px)',
            paddingBottom: 'calc(max(var(--tg-content-safe-area-inset-bottom, 0px), env(safe-area-inset-bottom, 0px)) + 20px)',
          }}
        >
          {isLoading ? (
            <SkeletonCard />
          ) : (
            <>
              <AnimatePresence custom={exitDirection}>
                {currentMovie && (
                  <MovieCard
                    key={cardSeq}
                    movie={currentMovie}
                    onSwipe={handleSwipe}
                    exitDirection={exitDirection}
                  />
                )}
              </AnimatePresence>
              {isLoadingNext && <SkeletonCard />}
              {!currentMovie && !isLoadingNext && (
                <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                  Нет доступных фильмов
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Match Overlay */}
      {matchedMovie && (
        <MatchOverlay
          movie={matchedMovie}
          onDismiss={() => setMatchedMovie(null)}
        />
      )}
    </div>
  );
}

export default App;

// Dev-only helper: inline to keep things simple
function DevTelegramIdSetter({ onSet }: { onSet: (id: number) => void }) {
  const [value, setValue] = useState<string>('');
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        placeholder="Enter test Telegram ID"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="rounded-md border border-input px-3 py-2"
      />
      <button
        onClick={() => {
          const parsed = Number(value);
          if (!Number.isNaN(parsed) && parsed > 0) {
            localStorage.setItem('telegramId', String(parsed));
            onSet(parsed);
          }
        }}
        className="rounded-md border border-border bg-white px-3 py-2 text-sm hover:bg-gray-50"
      >
        Set
      </button>
      <button
        onClick={() => {
          localStorage.removeItem('telegramId');
          onSet(null as unknown as number); // set to null via parent
        }}
        className="rounded-md border border-border bg-white px-3 py-2 text-sm hover:bg-gray-50"
      >
        Clear
      </button>
    </div>
  );
}
