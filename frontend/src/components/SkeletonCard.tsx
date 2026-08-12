// Скелетон карточки фильма: та же геометрия, что и у MovieCard (на весь экран),
// чтобы первичная загрузка не дёргала layout при появлении реальной карточки.
export const SkeletonCard = () => {
  return (
    <div className="absolute inset-0">
      <div className="relative h-full w-full rounded-3xl overflow-hidden shadow-2xl bg-card">
        {/* Плейсхолдер постера */}
        <div className="absolute inset-0 animate-pulse bg-muted" />

        {/* Плейсхолдеры текста (инфо-панель) */}
        <div className="absolute bottom-24 left-0 right-0 px-6">
          <div className="rounded-3xl p-5 space-y-3 border border-white/20 bg-gradient-to-b from-white/10 to-white/5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 space-y-2">
                <div className="h-6 w-2/3 animate-pulse rounded-md bg-muted-foreground/20" />
                <div className="h-4 w-1/2 animate-pulse rounded-md bg-muted-foreground/15" />
              </div>
              <div className="h-8 w-16 animate-pulse rounded-full bg-muted-foreground/20" />
            </div>
            <div className="h-4 w-full animate-pulse rounded-md bg-muted-foreground/15" />
          </div>
        </div>
      </div>
    </div>
  );
};
