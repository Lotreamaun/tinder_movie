// Предзагрузка изображений (постеров) до их показа, чтобы карточка не «прыгала»
// и не показывала пустоту при поздней загрузке.

export function preloadImage(src: string | null | undefined): void {
  if (!src) return;
  const img = new Image();
  img.src = src;
}
