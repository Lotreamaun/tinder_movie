// Компонент для отображения оверлея при нахождении матча
import { Heart } from "lucide-react";
import type { Movie } from '../types/movie_types';

interface MatchOverlayProps {
  movie: Movie;
  onDismiss: () => void;
}

export const MatchOverlay = ({ movie, onDismiss }: MatchOverlayProps) => {
  const rating = typeof movie.rating === 'number' ? movie.rating : Number(movie.rating ?? NaN);
  const displayRating = Number.isFinite(rating) ? rating.toFixed(1) : 'N/A';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={onDismiss}
    >
      <div
        className="relative w-[85%] max-w-sm rounded-3xl overflow-hidden shadow-2xl animate-match-pop"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Poster Background */}
        <div className="absolute inset-0">
          <img
            src={movie.posterUrl}
            alt={movie.title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent" />
        </div>

        {/* Content */}
        <div className="relative flex flex-col items-center justify-end min-h-[400px] px-6 pb-8 text-white">
          {/* Match Icon + Title */}
          <div className="flex flex-col items-center mb-6 animate-scale-in">
            <div className="relative mb-4">
              <div className="w-20 h-20 rounded-full bg-success/90 backdrop-blur-md flex items-center justify-center shadow-[0_0_40px_rgba(34,197,94,0.5)] animate-pulse-glow">
                <Heart className="w-10 h-10 text-white" fill="currentColor" />
              </div>
            </div>

            <h2 className="text-3xl font-extrabold text-center drop-shadow-lg mb-1">
              🎬 Найден матч!
            </h2>
          </div>

          {/* Movie Info Card - Liquid Glass */}
          <div className="w-full backdrop-blur-[40px] bg-gradient-to-b from-white/15 to-white/5 rounded-3xl p-5 space-y-3 shadow-[0_8px_32px_0_rgba(0,0,0,0.1)] border border-white/20 animate-scale-in">
            <div className="text-center space-y-2">
              <h3 className="text-2xl font-bold drop-shadow-lg">{movie.title}</h3>
              {movie.year && (
                <p className="text-sm opacity-90 drop-shadow-md">{movie.year}</p>
              )}
              {movie.titleOriginal && movie.titleOriginal !== movie.title && (
                <p className="text-xs opacity-75">{movie.titleOriginal}</p>
              )}
            </div>

            {/* Rating Badge */}
            <div className="flex justify-center">
              <div className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-white/25 backdrop-blur-xl border border-white/30 shadow-lg">
                <span className="text-lg">⭐</span>
                <span className="text-lg font-bold">{displayRating}</span>
              </div>
            </div>
          </div>

          {/* Subtitle */}
          <p className="mt-4 text-sm text-center opacity-90 animate-scale-in">
            Все участники группы лайкнули этот фильм!
          </p>

          {/* Dismiss Hint */}
          <p className="mt-3 text-xs text-center opacity-60 animate-fade-in-delayed">
            Нажмите в любом месте, чтобы продолжить
          </p>
        </div>
      </div>
    </div>
  );
};
