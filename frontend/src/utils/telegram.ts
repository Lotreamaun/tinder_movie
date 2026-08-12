// Ожидание инициализации Telegram WebApp SDK перед определением личности.
// Пока SDK не дал initData, приложение не должно показывать заглушку «Telegram ID not set».

const TELEGRAM_INIT_TIMEOUT_MS = 2000;
const TELEGRAM_INIT_POLL_MS = 50;

/**
 * Возвращает Telegram user id после готовности SDK.
 * - Вне Telegram (SDK отсутствует) — сразу null.
 * - В Telegram — ждёт появления initData с коротким retry/таймаутом.
 */
export function getTelegramUserId(): Promise<number | null> {
  return new Promise((resolve) => {
    const tg = window.Telegram?.WebApp;
    if (!tg) {
      resolve(null);
      return;
    }

    const startedAt = Date.now();
    const poll = () => {
      if (tg.initData && tg.initDataUnsafe?.user?.id) {
        resolve(tg.initDataUnsafe.user.id);
        return;
      }
      if (Date.now() - startedAt > TELEGRAM_INIT_TIMEOUT_MS) {
        resolve(null);
        return;
      }
      window.setTimeout(poll, TELEGRAM_INIT_POLL_MS);
    };
    poll();
  });
}

/**
 * Блокирует вертикальные свайпы в Telegram, чтобы окно mini-app не сворачивалось,
 * когда пользователь горизонтально свайпает карточку.
 */
export function disableVerticalSwipes(): void {
  window.Telegram?.WebApp.disableVerticalSwipes?.();
}
