# PROGRESS — Bajarilgan ishlar jurnali

> Bu fayl har sessiyada ishni tez davom ettirish uchun. Yangi sessiya boshlanganda **avval shu faylni o'qing**, so'ng `docs/tasks.md` ni ko'ring.

## Hozirgi holat

**Bosqich:** 1 — Skelet (poydevor)
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

## Jarayonda 🔄

- [ ] GitHub repo yaratish va birinchi push (GitHub login kutilmoqda)
- [ ] Backend FastAPI skeleti
- [ ] Frontend Next.js skeleti
- [ ] Docker Compose

## Keyingi qadamlar ⏭️

1. GitHub login (`gh auth login`) → remote qo'shish → push
2. Backend: FastAPI app, DB ulanish, auth
3. Frontend: login + dashboard
4. Birinchi OSINT moduli: username qidiruv

## Eslatmalar

- Har bosqichdan keyin: kod → `PROGRESS.md` yangilash → git commit + push.
- Commit xabarlari qisqa va aniq (ingliz tilida), prefiks bilan: `feat:`, `fix:`, `docs:`, `chore:`.
