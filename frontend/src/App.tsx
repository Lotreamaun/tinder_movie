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
  const [movieQueue, setMovieQueue] = useState<Movie[]>([]);

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

      // После успешного свайпа — берём следующий фильм из очереди
      if (movieQueue.length > 0) {
        const [nextMovie, ...rest] = movieQueue;
        setCurrentMovie(nextMovie);
        setMovieQueue(rest);
      } else {
        // Если очередь пуста — загружаем ещё один фильм
        const nextMovie = await getRandomMovie();
        setCurrentMovie(nextMovie);
      }

      // Подгружаем ещё один фильм, если в очереди мало
      if (movieQueue.length < 3) {
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