import { useState, useEffect, useRef, useCallback } from 'react';
import { MovieCard } from './components/MovieCard';
import { MatchOverlay } from './components/MatchOverlay';
import { getRandomMovie, createSwipe, getMyRoom, ApiError } from './services/api';
import './App.css';
import type { Movie } from './types/movie_types';

function App() {
  // 1. Текущий фильм
  const [currentMovie, setCurrentMovie] = useState<Movie | null>(null);

  // 2. Очередь фильмов (предзагрузка)
  const [_movieQueue, setMovieQueue] = useState<Movie[]>([]);

  // 3. Состояние загрузки
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 4. Ошибка
  const [error, setError] = useState<string | null>(null);

  // 5. Загрузка при свайпе
  const [isSwipeInProgress, setIsSwipeInProgress] = useState<boolean>(false);

  // 6. Telegram ID
  const [telegramId, setTelegramId] = useState<number | null>(null);

  // 7. Участники комнаты (для групповых свайпов)
  const [groupParticipants, setGroupParticipants] = useState<number[]>([]);

  // 8. Мэтч — фильм, по которому найден матч
  const [matchedMovie, setMatchedMovie] = useState<Movie | null>(null);

  // Ref-копия очереди — чтобы handleSwipe всегда видел актуальное значение
  const movieQueueRef = useRef<Movie[]>(_movieQueue);

  useEffect(() => {
    movieQueueRef.current = _movieQueue;
  }, [_movieQueue]);

  // Загружаем первый фильм и telegramId при монтировании компонента
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // 1. Пробуем получить реальный telegramId из Telegram WebApp API
        const tg = window.Telegram?.WebApp;
        const tgUserId = tg?.initDataUnsafe?.user?.id;

        if (tgUserId) {
          setTelegramId(tgUserId);
          console.log('Telegram ID from WebApp:', tgUserId);
        } else {
          // 2. Фоллбэк: localStorage (для тестов в браузере)
          const storedTelegramId = localStorage.getItem('telegramId');
          if (storedTelegramId) {
            setTelegramId(Number(storedTelegramId));
            console.log('Telegram ID from localStorage:', storedTelegramId);
          } else {
            // 3. Dev fallback: .env (только локальная разработка)
            const devId = import.meta.env.VITE_DEV_TELEGRAM_ID;
            if (import.meta.env.DEV && devId) {
              const parsed = Number(devId);
              if (!Number.isNaN(parsed)) {
                setTelegramId(parsed);
                console.warn('Using VITE_DEV_TELEGRAM_ID from .env:', parsed);
              }
            }
          }
        }

        // Загружаем комнату пользователя (нужно для групповых свайпов)
        const currentTgId = tgUserId || (localStorage.getItem('telegramId') ? Number(localStorage.getItem('telegramId')) : null);
        if (currentTgId) {
          const room = await getMyRoom(currentTgId);
          if (room && room.participantIds) {
            setGroupParticipants(room.participantIds);
            console.log('Room participants:', room.participantIds);
          } else {
            console.warn('User is not in any room — swipes require 2+ participants');
          }
        }

        setError(null);
        setIsLoading(true);

        // Загружаем 5 фильмов заранее
        const movies = await Promise.all([
          getRandomMovie(),
          getRandomMovie(),
          getRandomMovie(),
          getRandomMovie(),
          getRandomMovie(),
        ]);

        setMovieQueue(movies);
        setCurrentMovie(movies[0]);
        setMovieQueue(prev => prev.slice(1)); // Убираем первый фильм из очереди
        if (import.meta.env.DEV) {
          console.log('movie (first fetched):', movies[0]);
        }
      } catch (err) {
        console.error('Failed to initialize app:', err);
        setError(err instanceof ApiError ? err.message : 'Failed to initialize app');
      } finally {
        setIsLoading(false);
      }
    };

    initializeApp();
  }, []);

  // Функция для обработки свайпа — через useCallback чтобы всегда видеть актуальный currentMovie
  const handleSwipe = useCallback(async (swipeType: 'like' | 'dislike') => {
    if (!currentMovie || isSwipeInProgress || !telegramId) return;

    if (groupParticipants.length < 2) {
      setError('Нужно минимум 2 участника в комнате для свайпов');
      return;
    }

    try {
      setIsSwipeInProgress(true);
      setError(null);

      const swipeResult = await createSwipe({
        movieId: currentMovie.id,
        swipeType,
        groupParticipants,
        telegramId,
      });

      // Проверяем, найден ли мэтч
      if (swipeResult?.matchFound) {
        setMatchedMovie(currentMovie);
      }

      // Берём следующий фильм из очереди (через ref — всегда актуально)
      const queue = movieQueueRef.current;

      if (queue.length > 0) {
        const [next, ...rest] = queue;
        setCurrentMovie(next);
        setMovieQueue(rest);

        // Предзагружаем если осталось меньше 3
        if (rest.length < 3) {
          getRandomMovie().then(m => {
            setMovieQueue(q => [...q, m]);
          });
        }
      } else {
        // Очередь пуста — загружаем новый
        const movie = await getRandomMovie();
        setCurrentMovie(movie);
        // Предзагружаем следующий в фоне
        getRandomMovie().then(m => {
          setMovieQueue([m]);
        });
      }

    } catch (err) {
      console.error('Failed to create swipe:', err);
      setError(err instanceof ApiError ? err.message : 'Failed to create swipe');
    } finally {
      setIsSwipeInProgress(false);
    }
  }, [currentMovie, isSwipeInProgress, telegramId, groupParticipants]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container py-4 flex flex-col">
        {/* Dev/UX Banner when telegramId is missing */}
        {!telegramId && (
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
            <div className="font-semibold">Error</div>
            <div className="text-sm">{error}</div>
          </div>
        )}

        <div className="movie-container flex-1">
          {isLoading ? (
            <div className="loading">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
            </div>
          ) : currentMovie ? (
            <MovieCard
              movie={currentMovie}
              onSwipe={handleSwipe}
              disabled={isSwipeInProgress}
              className="h-full"
            />
          ) : (
            <div className="flex h-[60vh] items-center justify-center text-muted-foreground">No movie available</div>
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