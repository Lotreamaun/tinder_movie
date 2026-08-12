import { useRef, useState } from "react";
import { motion, animate, useMotionValue, useTransform, type Variants } from "framer-motion";
import { Heart, X } from "lucide-react";
import type { Movie } from "../types/movie_types";
import {
  SWIPE_DISTANCE_THRESHOLD,
  SWIPE_VELOCITY_THRESHOLD,
  SWIPE_ROTATION_ANGLE,
  SWIPE_ROTATION_RANGE,
  SWIPE_DRAG_ELASTIC,
  SWIPE_RETURN_SPRING,
} from "../config/swipe";

export type SwipeDirection = "like" | "dislike";
export type ExitDirection = "left" | "right";

interface MovieCardProps {
  movie: Movie;
  onSwipe: (direction: SwipeDirection) => void;
  exitDirection: ExitDirection | null;
  style?: React.CSSProperties;
}

// Вход (scale-in), центр и вылет (throw) в направлении жеста.
// custom — направление последнего свайпа, задаётся через <AnimatePresence custom=...>.
const cardVariants: Variants = {
  enter: { x: 0, y: 0, opacity: 0, scale: 0.9 },
  center: { x: 0, y: 0, opacity: 1, scale: 1 },
  exit: (exitDirection: ExitDirection) => ({
    x: exitDirection === "right" ? 500 : -500,
    y: 0,
    opacity: 0,
    scale: 0.9,
    transition: { duration: 0.3, ease: "easeIn" },
  }),
};

export const MovieCard = ({ movie, onSwipe, exitDirection, style }: MovieCardProps) => {
  const [showDescription, setShowDescription] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  // Прерывание жеста (pointercancel): framer-motion тоже вызывает onDragEnd — помечаем
  // отмену, чтобы не засчитать свайп, а вернуть карточку в исходное положение.
  const wasCancelledRef = useRef(false);

  // Позиция/наклон карточки живут в MotionValue: обновление через rAF без ререндера
  // React на каждый кадр — это и даёт 60 FPS во время drag.
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-SWIPE_ROTATION_RANGE, SWIPE_ROTATION_RANGE], [-SWIPE_ROTATION_ANGLE, SWIPE_ROTATION_ANGLE]);
  const likeOpacity = useTransform(x, [0, 120], [0, 1]);
  const dislikeOpacity = useTransform(x, [0, -120], [0, 1]);

  const returnToOrigin = () => {
    animate(x, 0, SWIPE_RETURN_SPRING);
  };

  // Pointer Events (framer-motion drag построен на них и сам захватывает указатель).
  // Не перехватываем нажатия на кнопках — они обрабатывают клик сами.
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest("button")) return;
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  // Прерывание жеста браузером (pointercancel/touchcancel): карточка возвращается
  // в исходное положение, намерение пользователя не теряется.
  const handlePointerCancel = () => {
    wasCancelledRef.current = true;
    setIsDragging(false);
    returnToOrigin();
  };

  const handleDragEnd = (_e: MouseEvent | TouchEvent | PointerEvent, info: { offset: { x: number }; velocity: { x: number } }) => {
    setIsDragging(false);

    // Отменённый жест не засчитывается как свайп.
    if (wasCancelledRef.current) {
      wasCancelledRef.current = false;
      returnToOrigin();
      return;
    }

    const { offset, velocity } = info;
    const overDistance = Math.abs(offset.x) > SWIPE_DISTANCE_THRESHOLD;
    const fastEnough = Math.abs(velocity.x) > SWIPE_VELOCITY_THRESHOLD;

    if (overDistance || fastEnough) {
      // Свайп засчитан: карточку уводит AnimatePresence (exit) в направлении жеста.
      onSwipe(offset.x > 0 ? "like" : "dislike");
    } else {
      // Недостаточный жест — пружинный возврат в исходное положение.
      returnToOrigin();
    }
  };

  return (
    <div className="absolute inset-0" style={style}>
      <motion.div
        className="movie-card relative h-full w-full rounded-3xl overflow-hidden shadow-2xl bg-card"
        variants={cardVariants}
        custom={exitDirection ?? "right"}
        initial="enter"
        animate="center"
        exit="exit"
        style={{ x, rotate }}
        drag="x"
        dragElastic={SWIPE_DRAG_ELASTIC}
        dragMomentum={false}
        onPointerDown={handlePointerDown}
        onPointerCancel={handlePointerCancel}
        onDragStart={() => {
          wasCancelledRef.current = false;
          setIsDragging(true);
        }}
        onDragEnd={handleDragEnd}
      >
          {/* Poster Image */}
          <div className="absolute inset-0">
            <img
              src={movie.posterUrl || "/poster-fallback.jpg"}
              alt={movie.title}
              className="w-full h-full object-cover"
              loading="lazy"
              onError={(e) => {
                const img = e.currentTarget as HTMLImageElement & { dataset: { fallbackApplied?: string } };
                if (img.dataset.fallbackApplied === 'true') {
                  const svg = encodeURIComponent(
                    `<svg xmlns='http://www.w3.org/2000/svg' width='400' height='600'><rect width='100%' height='100%' fill='#222'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='#aaa' font-family='system-ui, sans-serif' font-size='24'>No Poster</text></svg>`
                  );
                  img.onerror = null;
                  img.src = `data:image/svg+xml;charset=UTF-8,${svg}`;
                  return;
                }
                img.dataset.fallbackApplied = 'true';
                img.src = '/poster-fallback.jpg';
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
          </div>

          {/* Swipe Indicators */}
          {isDragging && (
            <>
              <motion.div
                className="absolute top-8 right-8"
                style={{ opacity: likeOpacity }}
              >
                <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-success/90">
                  <Heart className="w-6 h-6 text-success-foreground" fill="currentColor" />
                  <span className="text-success-foreground font-semibold">ЛАЙК</span>
                </div>
              </motion.div>
              <motion.div
                className="absolute top-8 left-8"
                style={{ opacity: dislikeOpacity }}
              >
                <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-destructive/90">
                  <X className="w-6 h-6 text-destructive-foreground" />
                  <span className="text-destructive-foreground font-semibold">ПРОПУСК</span>
                </div>
              </motion.div>
            </>
          )}

          {/* Movie Info - Liquid Glass Style (backdrop-blur, чтобы текст не сливался с постером) */}
          <div className="absolute bottom-24 left-0 right-0 px-6 text-white pointer-events-none">
            <div
              className="bg-gradient-to-b from-black/40 to-black/20 backdrop-blur-xl rounded-3xl p-5 space-y-3 shadow-[0_8px_32px_0_rgba(0,0,0,0.25)] border border-white/20"
              style={{ pointerEvents: 'auto' }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h2 className="text-2xl font-bold mb-1 drop-shadow-lg">{movie.title}</h2>
                  <p className="text-sm opacity-90 drop-shadow-md">{movie.titleOriginal}</p>
                </div>
                <div className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/25 border border-white/30 shadow-lg">
                  <span className="text-lg font-bold">⭐</span>
                  {(() => {
                    const numericRating = typeof movie.rating === 'number' ? movie.rating : Number(movie.rating ?? NaN);
                    const display = Number.isFinite(numericRating) ? numericRating.toFixed(1) : 'N/A';
                    return <span className="text-lg font-semibold drop-shadow-md">{display}</span>;
                  })()}
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
              onClick={() => onSwipe("dislike")}
              className="w-16 h-16 rounded-full bg-white/20 border border-white/30 backdrop-blur-md shadow-[0_8px_32px_0_rgba(0,0,0,0.15)] flex items-center justify-center transition-all active:scale-90 hover:bg-white/30 hover:shadow-[0_8px_40px_0_rgba(0,0,0,0.2)]"
            >
              <X className="w-8 h-8 text-white drop-shadow-lg" />
            </button>
            <button
              onClick={() => onSwipe("like")}
              className="w-16 h-16 rounded-full bg-white/20 border border-white/30 backdrop-blur-md shadow-[0_8px_32px_0_rgba(0,0,0,0.15)] flex items-center justify-center transition-all active:scale-90 hover:bg-white/30 hover:shadow-[0_8px_40px_0_rgba(0,0,0,0.2)]"
            >
              <Heart className="w-8 h-8 text-white drop-shadow-lg" fill="currentColor" />
            </button>
          </div>
        </motion.div>
    </div>
  );
};
