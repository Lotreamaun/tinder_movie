export interface Movie {
  id: string; // UUID
  kinopoiskId: number;
  title: string;
  titleOriginal: string | null;
  year: number;
  genre: string;
  posterUrl: string;
  description: string | null;
  rating: number | null;
  createdAt: string; // ISO date string
  isActive: boolean;
}

export interface SwipeVote {
  groupId: string;
  movieId: string;
  voteType: 'like' | 'dislike';
}

// Ответ при получении случайного фильма
export interface GetRandomMovieResponse {
  movie: Movie;
  sessionId: string;
}

// Ответ при голосовании
export interface VoteResponse {
  success: boolean;
  matchFound: boolean;
  remainingVotes: number;
}

export interface SessionToken {
  token: string;
  expiresAt: string; // ISO date string
  userId: string; // Telegram ID
}

export interface SwipeResponse {
  id: string;
  userId: string;
  movieId: string;
  swipeType: 'like' | 'dislike';
  swipedAt: string; // ISO date string
  groupParticipants: number[];
  matchFound?: boolean; // Опциональное поле - присутствует только при лайке
}