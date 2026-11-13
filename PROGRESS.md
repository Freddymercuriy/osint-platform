# PROGRESS — Bajarilgan ishlar jurnali

> Bu fayl har sessiyada ishni tez davom ettirish uchun. Yangi sessiya boshlanganda **avval shu faylni o'qing**, so'ng `docs/tasks.md` ni ko'ring.

## Hozirgi holat

**Bosqich:** 4 tugadi (username qidiruv ishlaydi) → 5 (yangi modullar) keyingi
**Oxirgi yangilanish:** 2026-11-13

## Stack (tasdiqlangan)

- Frontend: Next.js + TypeScript + Tailwind
- Backend: Python FastAPI
- Database: PostgreSQL
- Infra: Docker Compose

## Bajarilgan ✅

- [x] Git repo init, `.gitignore`, `README.md`
- [x] `PROGRESS.md`, `docs/architecture.md`, `docs/tasks.md`
- [x] `.claude/agents/` — 5 ta agent ta'rifi (frontend, backend, database, osint-collector, devops)
- [x] GitHub repo (private): https://github.com/Freddymercuriy/osint-platform
- [x] Backend FastAPI skeleti: config, async DB, JWT auth (register/login/me), User modeli
- [x] OSINT collector interfeysi (`BaseCollector`, `CollectResult`)
- [x] Docker: `backend/Dockerfile`, `docker-compose.yml` (db + backend) — test qilindi, ishlayapti
- [x] Frontend Next.js 14 + TS + Tailwind: home, login, register, dashboard
- [x] `lib/api.ts` — backend bilan ishlash (register/login/me, token localStorage'da)
- [x] Frontend build + type-check o'tdi, dev server `/login` → 200 ✅
- [x] `frontend/Dockerfile` (standalone, kelajak uchun)
- [x] **Username qidiruv moduli (Bosqich 4):**
  - `SearchJob` + `Result` modellar (qidiruv tarixi DB da)
  - `UsernameCollector` — 13 ta ochiq saytni async tekshiradi (GitHub, GitLab,
    Twitch, Telegram, Medium, Dev.to, Replit, SoundCloud, Pinterest, Steam,
    HackerNews, Keybase, Reddit). Bloklovchi saytlar "error" sifatida qaytadi.
  - `/api/search/username`, `/api/search/history`, `/api/search/jobs/{id}` endpointlar
  - Frontend: `/dashboard/username` qidiruv sahifasi (status badge, saralash)
  - To'liq test: "torvalds" → 13 tekshirildi, 5 topildi ✅

## Jarayonda 🔄

- (bo'sh) — keyingi bosqichga tayyor

## Keyingi qadamlar ⏭️

1. Yangi collector: email/telefon yoki domen/WHOIS (xohishga qarab)
2. Qidiruv tarixini frontend'da ko'rsatish sahifasi (`/api/search/history` bor)
3. Collector'larni `name` bo'yicha registry orqali ulash (yangi modul qo'shishni osonlashtiradi)
4. (keyin) Alembic migratsiyalar — hozir dev'da `create_all`
5. (keyin) Next 15 ga ko'chish — qolgan npm audit ogohlantirishlari uchun

## Muhit eslatmalari ⚙️

- Bu mashinada **`docker compose` v2 yo'q**, faqat eski `docker-compose` v1.29 bor.
- v1 yangi Docker engine bilan **rebuild**da `KeyError: ContainerConfig` beradi.
  Yechim: kodni o'zgartirgach `docker-compose restart backend` (bind-mount tufayli kod yangilanadi),
  yoki to'liq qayta qurish kerak bo'lsa avval `docker-compose down` qilib keyin `up --build`.
- `gh` CLI `~/.local/bin/gh` da (sudosiz o'rnatilgan). GitHub user: `Freddymercuriy`.
- `sudo` parol so'raydi — assistant ishlata olmaydi.
- Frontend hozircha Docker'siz: `cd frontend && npm run dev` (http://localhost:3000).
- Next.js 14.2.35 (eng so'nggi 14.x). 2 ta npm audit ogohlantirishi qoldi —
  faqat Next 15 da tuzaladi, ishlatilmaydigan funksiyalarga tegishli.

## Eslatmalar

- Har bosqichdan keyin: kod → `PROGRESS.md` yangilash → git commit + push.
- Commit xabarlari qisqa va aniq (ingliz tilida), prefiks bilan: `feat:`, `fix:`, `docs:`, `chore:`.
