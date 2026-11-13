# CLAUDE.md — loyiha yo'riqnomasi

Bu OSINT platformasi (web dastur). **Yangi sessiya boshida avval [`PROGRESS.md`](./PROGRESS.md) ni o'qi**, so'ng [`docs/tasks.md`](./docs/tasks.md).

## Stack
Next.js + TypeScript + Tailwind (frontend) · FastAPI (backend) · PostgreSQL · Docker Compose.

## Agentlar
`.claude/agents/` da maxsus agentlar bor — ishni mos agentga topshir:
- `backend` — FastAPI API/logika
- `frontend` — Next.js UI
- `database` — modellar, migratsiyalar
- `osint-collector` — OSINT yig'uvchi modullar
- `devops` — Docker, deploy, git

## Ish tartibi (muhim)
Har bir tugatilgan bosqichdan keyin:
1. Kodni yoz/tuzat.
2. `PROGRESS.md` va kerak bo'lsa `docs/tasks.md` ni yangila.
3. `git add -A && git commit` (ingliz tilida, `feat:`/`fix:`/`docs:`/`chore:` prefiksi bilan).
4. `git push`.

## Axloq
Faqat ochiq (public) manbalar. Maxfiy kalitlar `.env` da, git'ga tushmaydi.
