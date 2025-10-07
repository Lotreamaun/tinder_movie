import { useState, useEffect } from 'react';
import { MovieCard } from './components/MovieCard';
import { getRandomMovie, createSwipe, ApiError } from './services/api';
import type { Movie } from './types/movie_types';
import reactLogo from './assets/react.svg';
import viteLogo from '/vite.svg';
import './App.css';

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
    <>
      {/* Dev/UX Banner when telegramId is missing */}
      {!telegramId && (
        <div style={{
          background: '#fff3cd',
          color: '#664d03',
          padding: '10px 14px',
          border: '1px solid #ffecb5',
          borderRadius: 8,
          margin: '10px 0'
        }}>
          <div style={{ marginBottom: 8 }}>
            <strong>Telegram ID not set.</strong> Swipes are disabled. Set localStorage key <code>telegramId</code> or use env <code>VITE_DEV_TELEGRAM_ID</code> in dev.
          </div>
          {import.meta.env.DEV && (
            <DevTelegramIdSetter onSet={(id) => setTelegramId(id)} />
          )}
        </div>
      )}

      <div>
        <a href="https://vite.dev" target="_blank" rel="noreferrer">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank" rel="noreferrer">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Vite + React</h1>

      {/* Показываем ошибку, если есть */}
      {error && (
        <div style={{ color: 'red', padding: '10px', backgroundColor: '#ffe6e6', margin: '10px' }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Показываем спиннер, если загружаем */}
      {isLoading ? (
        <div className="loading">Loading movie...</div>
      ) : currentMovie ? (
        <MovieCard
          movie={currentMovie}
          onSwipe={handleSwipe} // передаём функцию, которая принимает 'like' | 'dislike'
          disabled={isSwipeInProgress} // блокируем карточку при загрузке
        />
      ) : (
        <p>No movie available</p>
      )}

      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  );
}

export default App;

// Dev-only helper: inline to keep things simple
function DevTelegramIdSetter({ onSet }: { onSet: (id: number) => void }) {
  const [value, setValue] = useState<string>('');
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <input
        type="number"
        placeholder="Enter test Telegram ID"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        style={{ padding: 6, borderRadius: 6, border: '1px solid #d3d3d3' }}
      />
      <button
        onClick={() => {
          const parsed = Number(value);
          if (!Number.isNaN(parsed) && parsed > 0) {
            localStorage.setItem('telegramId', String(parsed));
            onSet(parsed);
          }
        }}
        style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #c7c7c7', background: '#fff' }}
      >
        Set
      </button>
      <button
        onClick={() => {
          localStorage.removeItem('telegramId');
          onSet(null as unknown as number); // set to null via parent
        }}
        style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #c7c7c7', background: '#fff' }}
      >
        Clear
      </button>
    </div>
  );
}