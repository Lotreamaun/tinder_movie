// Константы жеста свайпа карточки фильма (см. design.md, «Жесты: Pointer Events + framer-motion drag»).
// Вынесены в отдельный модуль, чтобы подбирать пороги на устройстве без правки компонента.

/** Минимальное смещение по X (px), после которого свайп засчитывается по дистанции. */
export const SWIPE_DISTANCE_THRESHOLD = 100;

/** Минимальная скорость флика (px/s) для засчёта свайпа, даже если дистанция не достигнута. */
export const SWIPE_VELOCITY_THRESHOLD = 500;

/** Угол наклона карточки (deg) при полном смещении к краю (см. ROTATION_RANGE). */
export const SWIPE_ROTATION_ANGLE = 12;

/** Смещение по X, при котором наклон достигает SWIPE_ROTATION_ANGLE. */
export const SWIPE_ROTATION_RANGE = 250;

/** Эластичность drag-жеста: доля «перетяга» за пределы перед пружинным возвратом. */
export const SWIPE_DRAG_ELASTIC = 0.6;

/** Параметры пружинного возврата карточки при отменённом/недостаточном жесте. */
export const SWIPE_RETURN_SPRING = { type: "spring", stiffness: 400, damping: 40 } as const;
