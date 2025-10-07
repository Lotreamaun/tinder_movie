# Frontend

## Styling

This app uses Tailwind CSS with CSS variables (shadcn-style tokens) for theming.

- Dark mode is enabled via the `.dark` class on `html` or `body`.
- Theme tokens are defined in `src/index.css` and mapped in `tailwind.config.ts`.
- Animations are powered by `tailwindcss-animate` plus a custom `animate-scale-in`.

## Development

1. Install dependencies:
   ```bash
   npm install
   ```
2. Run dev server:
   ```bash
   npm run dev
   ```

## Environment Variables

- `VITE_API_BASE_URL` – backend API base URL (e.g. `http://localhost:8000`)
- `VITE_DEV_TELEGRAM_ID` – optional dev fallback telegram ID for local testing

Create a `.env` file or use shell env vars. See `env.example` in repo root.

## Project Structure

- `src/components/MovieCard.tsx` – swipeable movie card UI
- `src/services/api.ts` – API client
- `src/types/movie_types.ts` – TypeScript types
- `src/App.tsx` – app shell and state management

## Tech Stack

- React 19, TypeScript, Vite 7
- Tailwind CSS, tailwindcss-animate
- Axios, Lucide React


