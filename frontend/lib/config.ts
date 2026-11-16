/**
 * Backend API manzili — bitta joyda.
 *
 * `NEXT_PUBLIC_API_URL` (frontend/.env.local) dev server / build ishga tushganda kodga yoziladi — o'zgartirgach
 * `npm run dev` ni qayta ishga tushiring. Berilmagan bo'lsa: brauzerda sahifa ochilgan host'ning 8000-porti
 * (http://localhost:3000 → http://localhost:8000, http://192.168.1.50:3000 → http://192.168.1.50:8000).
 */
const BACKEND_PORT = 8000;

function fallback(): string {
  if (typeof window !== "undefined") return `${window.location.protocol}//${window.location.hostname}:${BACKEND_PORT}`;
  return `http://127.0.0.1:${BACKEND_PORT}`; // server tomonida (SSR) — shu mashinadagi backend
}

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || fallback()).replace(/\/+$/, "");
