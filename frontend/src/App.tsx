import { useState, useEffect } from 'react';
import { MovieCard } from './components/MovieCard';
import { getRandomMovie, createSwipe, ApiError } from './services/api';
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

  // 6. Telegram ID (временно из localStorage, можно заменить на вызов API)
  const [telegramId, setTelegramId] = useState<number | null>(null);

  // Загружаем первый фильм и telegramId при монтировании компонента
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // Попробуем получить telegramId из localStorage
        const storedTelegramId = localStorage.getItem('telegramId');
        if (storedTelegramId) {
          setTelegramId(Number(storedTelegramId));
        } else {
          // Dev fallback для удобного локального теста
          const devId = import.meta.env.VITE_DEV_TELEGRAM_ID;
          if (import.meta.env.DEV && devId) {
            const parsed = Number(devId);
            if (!Number.isNaN(parsed)) {
              setTelegramId(parsed);
            }
          }
          // В реальном приложении: вызвать API, чтобы получить telegramId
          // const user = await api.getCurrentUser();
          // setTelegramId(user.telegramId);
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

  // Функция для обработки свайпа
  const handleSwipe = async (swipeType: 'like' | 'dislike') => {
    if (!currentMovie || isSwipeInProgress || !telegramId) return;

    try {
      setIsSwipeInProgress(true);
      setError(null); // Сбрасываем ошибку

      await createSwipe({
        movieId: currentMovie.id,
        swipeType,
        groupParticipants: [],
        telegramId,
      });

      // Поп и выбор следующего фильма + решение о предзагрузке — в одном функциональном апдейтере
      let needFetchNext = false;
      let needPreload = false;

      setMovieQueue(prev => {
        let next: Movie | null = null;
        let newQueue: Movie[] = prev;

        if (prev.length > 0) {
          const [first, ...rest] = prev;
          next = first;
          newQueue = rest;
        } else {
          next = null;
        }

        // Обновляем текущий фильм, рассчитанный из prev
        setCurrentMovie(next);

        // Фиксируем решения, чтобы выполнить асинхронные действия после апдейта очереди
        needFetchNext = next === null;
        needPreload = newQueue.length < 3;

        return newQueue;
      });

      // Если не было следующего фильма в очереди — загружаем новый
      if (needFetchNext) {
        const fetched = await getRandomMovie();
        setCurrentMovie(fetched);
      }

      // Если очередь стала короткой — предзагружаем ещё один
      if (needPreload) {
        const preload = await getRandomMovie();
        setMovieQueue(prev => [...prev, preload]);
      }

    } catch (err) {
      console.error('Failed to create swipe:', err);
      setError(err instanceof ApiError ? err.message : 'Failed to create swipe');
    } finally {
      setIsSwipeInProgress(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container py-4">
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

        <div className="movie-container">
          {isLoading ? (
            <div className="loading">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-muted border-t-primary" />
            </div>
          ) : currentMovie ? (
            <MovieCard
              movie={currentMovie}
              onSwipe={handleSwipe}
              disabled={isSwipeInProgress}
            />
          ) : (
            <div className="flex h-[60vh] items-center justify-center text-muted-foreground">No movie available</div>
          )}
        </div>
      </div>
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