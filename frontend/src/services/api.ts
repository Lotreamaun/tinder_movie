import axios, { AxiosError, type AxiosResponse } from 'axios';
import type { Movie, SwipeResponse } from '../types/movie_types';

// =============================================================================
// 1. Custom Error Class
// =============================================================================

export class ApiError extends Error {
  statusCode: number;
  details?: string;

  constructor(message: string, statusCode: number, details?: string) {
    super(message);
    this.statusCode = statusCode;
    this.details = details;
    this.name = 'ApiError';
  }
}

// =============================================================================
// 2. Case Conversion Utilities
// =============================================================================

/**
 * Рекурсивно преобразует ключи объекта из snake_case в camelCase
 */
export function snakeToCamel(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(snakeToCamel);
  }

  if (typeof obj === 'object') {
    const converted: Record<string, any> = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
        converted[camelKey] = snakeToCamel(obj[key]);
      }
    }
    return converted;
  }

  return obj; // примитивные значения (string, number, boolean и т.д.)
}

/**
 * Рекурсивно преобразует ключи объекта из camelCase в snake_case
 */
export function camelToSnake(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(camelToSnake);
  }

  if (typeof obj === 'object') {
    const converted: Record<string, any> = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const snakeKey = key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();
        converted[snakeKey] = camelToSnake(obj[key]);
      }
    }
    return converted;
  }

  return obj;
}

// =============================================================================
// 3. Axios Instance Configuration
// =============================================================================

// Определяем тип для обёртки ответа от бэкенда
interface ApiResponse<T> {
  data: T;
  error?: string;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000, // 10 секунд
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    if (import.meta.env.DEV) {
      console.log('→ API Request:', {
        method: config.method?.toUpperCase(),
        url: config.url,
        headers: config.headers,
        data: config.data,
      });
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response: AxiosResponse<ApiResponse<any>>) => {
    if (import.meta.env.DEV) {
      console.log('← API Response:', {
        status: response.status,
        url: response.config.url,
        data: response.data,
      });
    }

    // Преобразуем данные из snake_case в camelCase
    const transformedData = snakeToCamel(response.data.data);
    return transformedData;
  },
  (error: AxiosError) => {
    if (import.meta.env.DEV) {
      console.error('← API Error:', error);
    }

    // Сетевая ошибка или таймаут (нет response)
    if (!error.response) {
      throw new ApiError('Network error or timeout. Please check your connection.', 0);
    }

    const { status, data } = error.response;

    // Пытаемся получить сообщение об ошибке от бэкенда
    let errorMessage = 'An unexpected error occurred';
    let errorDetails: string | undefined;

    if (data && typeof data === 'object') {
      // Предполагаем, что бэкенд возвращает ошибку в формате { error: "..." }
      if ('error' in data && typeof data.error === 'string') {
        errorMessage = data.error;
      } else if ('detail' in data && typeof data.detail === 'string') {
        // Иногда FastAPI использует 'detail'
        errorMessage = data.detail;
      } else if ('message' in data && typeof data.message === 'string') {
        errorMessage = data.message;
      }

      // Сохраняем весь объект ошибки как детали (для отладки)
      errorDetails = JSON.stringify(data);
    }

    throw new ApiError(errorMessage, status, errorDetails);
  }
);

// =============================================================================
// 4. API Methods
// =============================================================================

/**
 * Получает случайный фильм с сервера
 */
export async function getRandomMovie(): Promise<Movie> {
    return api.get('/random');
  }

/**
 * Отправляет свайп (лайк/дизлайк) на сервер
 */
export async function createSwipe(params: {
  movieId: string;
  swipeType: 'like' | 'dislike';
  groupParticipants: number[];
  telegramId: number;
}): Promise<SwipeResponse> {
  const { telegramId, ...bodyParams } = params;

  // Преобразуем тело запроса в snake_case
  const snakeCaseBody = camelToSnake(bodyParams);

  return api.post('/swipes', snakeCaseBody, {
    headers: {
      telegram_id: telegramId.toString(), // Заголовок как строка
    },
  });
}

// =============================================================================
// 5. Export
// =============================================================================

export default {
  getRandomMovie,
  createSwipe,
};

// Экспортируем ApiError для использования в других частях приложения
// (уже экспортирован выше как `export class ApiError`)