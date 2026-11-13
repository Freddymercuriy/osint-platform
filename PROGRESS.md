# PROGRESS — Bajarilgan ishlar jurnali

> Bu fayl har sessiyada ishni tez davom ettirish uchun. Yangi sessiya boshlanganda **avval shu faylni o'qing**, so'ng `docs/tasks.md` ni ko'ring.

## Hozirgi holat

**Bosqich:** 2 tugadi → 3 (frontend) boshlanmoqda
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

## Jarayonda 🔄

- [ ] Frontend Next.js skeleti (login + dashboard)

## Keyingi qadamlar ⏭️

1. Frontend: Next.js + Tailwind, login/register, dashboard
2. Frontend konteynerini docker-compose ga qo'shish
3. Birinchi OSINT moduli: username qidiruv (collector + API + UI)
4. (keyin) Alembic migratsiyalar — hozir dev'da `create_all` ishlatilmoqda

## Muhit eslatmalari ⚙️

- Bu mashinada **`docker compose` v2 yo'q**, faqat eski `docker-compose` v1.29 bor.
- v1 yangi Docker engine bilan **rebuild**da `KeyError: ContainerConfig` beradi.
  Yechim: kodni o'zgartirgach `docker-compose restart backend` (bind-mount tufayli kod yangilanadi),
  yoki to'liq qayta qurish kerak bo'lsa avval `docker-compose down` qilib keyin `up --build`.
- `gh` CLI `~/.local/bin/gh` da (sudosiz o'rnatilgan). GitHub user: `Freddymercuriy`.
- `sudo` parol so'raydi — assistant ishlata olmaydi.

## Eslatmalar

- Har bosqichdan keyin: kod → `PROGRESS.md` yangilash → git commit + push.
- Commit xabarlari qisqa va aniq (ingliz tilida), prefiks bilan: `feat:`, `fix:`, `docs:`, `chore:`.
