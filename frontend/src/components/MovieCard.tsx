import { useState } from "react";
import { Heart, X } from "lucide-react";
import type { Movie } from '../types/movie_types'

interface MovieCardProps {
  movie: Movie;
  onSwipe: (direction: "like" | "dislike") => void;
  disabled?: boolean;
  style?: React.CSSProperties;
}

export const MovieCard = ({ movie, onSwipe, disabled, style }: MovieCardProps) => {
  const [showDescription, setShowDescription] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const handleTouchStart = (e: React.TouchEvent) => {
    if (disabled) return;
    const touch = e.touches[0];
    setDragStart({ x: touch.clientX, y: touch.clientY });
    setIsDragging(true);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (disabled) return;
    if (!dragStart) return;
    const touch = e.touches[0];
    const deltaX = touch.clientX - dragStart.x;
    const deltaY = touch.clientY - dragStart.y;
    setDragOffset({ x: deltaX, y: deltaY });
  };

  const handleTouchEnd = () => {
    if (disabled) return;
    if (!dragStart) return;
    
    const threshold = 100;
    if (Math.abs(dragOffset.x) > threshold) {
      if (dragOffset.x > 0) {
        onSwipe("like");
      } else {
        onSwipe("dislike");
      }
    }
    
    setDragStart(null);
    setDragOffset({ x: 0, y: 0 });
    setIsDragging(false);
  };

  const rotation = isDragging ? dragOffset.x / 20 : 0;
  const opacity = isDragging ? 1 - Math.abs(dragOffset.x) / 300 : 1;

  return (
    <div
      className="absolute inset-0 flex items-center justify-center p-4"
      style={style}
    >
      <div
        className="relative w-full h-full max-w-md rounded-3xl overflow-hidden shadow-2xl bg-card transition-transform touch-none"
        style={{
          transform: `translateX(${dragOffset.x}px) translateY(${dragOffset.y}px) rotate(${rotation}deg)`,
          opacity,
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {/* Poster Image */}
        <div className="absolute inset-0">
          <img
            src={movie.posterUrl}
            alt={movie.title}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => {
              e.currentTarget.onerror = null; // prevent infinite loop if fallback fails
              e.currentTarget.src = '/fallback_poster.jpg';
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        </div>

        {/* Swipe Indicators */}
        {isDragging && (
          <>
            <div
              className="absolute top-8 right-8 transition-opacity"
              style={{ opacity: Math.max(0, dragOffset.x / 150) }}
            >
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-success/90 backdrop-blur-md">
                <Heart className="w-6 h-6 text-success-foreground" fill="currentColor" />
                <span className="text-success-foreground font-semibold">ЛАЙК</span>
              </div>
            </div>
            <div
              className="absolute top-8 left-8 transition-opacity"
              style={{ opacity: Math.max(0, -dragOffset.x / 150) }}
            >
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-destructive/90 backdrop-blur-md">
                <X className="w-6 h-6 text-destructive-foreground" />
                <span className="text-destructive-foreground font-semibold">ПРОПУСК</span>
              </div>
            </div>
          </>
        )}

        {/* Movie Info - Liquid Glass Style */}
        <div className="absolute bottom-24 left-0 right-0 px-6 text-white pointer-events-none">
          <div 
            className="backdrop-blur-[40px] bg-gradient-to-b from-white/15 to-white/5 rounded-3xl p-5 space-y-3 shadow-[0_8px_32px_0_rgba(0,0,0,0.1)] border border-white/20"
            style={{ pointerEvents: 'auto' }}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h2 className="text-2xl font-bold mb-1 drop-shadow-lg">{movie.title}</h2>
                <p className="text-sm opacity-90 drop-shadow-md">{movie.titleOriginal}</p>
              </div>
              <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/25 backdrop-blur-xl border border-white/30 shadow-lg">
                <span className="text-lg font-bold">⭐</span>
                <span className="text-lg font-semibold drop-shadow-md">{movie.rating?.toFixed(1) ?? 'N/A'}</span>
              </div>
            </div>
            
            <button
              onClick={() => setShowDescription(!showDescription)}
              className="w-full text-sm font-medium text-white/95 hover:text-white transition-all text-left py-1"
            >
              {showDescription ? "Скрыть описание" : "Открыть описание"}
            </button>

            {showDescription && (
              <div className="pt-3 border-t border-white/25 animate-scale-in">
                <p className="text-sm leading-relaxed opacity-95 drop-shadow-md">{movie.description}</p>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons - Liquid Glass Style */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex gap-6 pointer-events-auto">
          <button
            onClick={() => !disabled && onSwipe("dislike")}
            disabled={disabled}
            className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-xl border border-white/30 shadow-[0_8px_32px_0_rgba(0,0,0,0.15)] flex items-center justify-center transition-all active:scale-90 hover:bg-white/30 hover:shadow-[0_8px_40px_0_rgba(0,0,0,0.2)]"
          >
            <X className="w-8 h-8 text-white drop-shadow-lg" />
          </button>
          <button
            onClick={() => !disabled && onSwipe("like")}
            disabled={disabled}
            className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-xl border border-white/30 shadow-[0_8px_32px_0_rgba(0,0,0,0.15)] flex items-center justify-center transition-all active:scale-90 hover:bg-white/30 hover:shadow-[0_8px_40px_0_rgba(0,0,0,0.2)]"
          >
            <Heart className="w-8 h-8 text-white drop-shadow-lg" fill="currentColor" />
          </button>
        </div>
      </div>
    </div>
  );
};