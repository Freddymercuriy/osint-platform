# OSINT Platform

Open-source intelligence (OSINT) yig'ish va tahlil qilish uchun web platforma.

> ⚠️ **Faqat qonuniy va axloqiy maqsadlar uchun.** Ushbu platforma ochiq (public) manbalardan ma'lumot yig'adi. Undan foydalanganda tegishli qonunlar va saytlarning foydalanish shartlariga rioya qiling.

## Texnologiyalar

| Qatlam | Texnologiya |
|--------|-------------|
| Frontend | Next.js (React + TypeScript) + Tailwind CSS |
| Backend | Python + FastAPI |
| Database | PostgreSQL |
| Infra | Docker Compose |

## Modullar (reja)

- [x] Loyiha skeleti, backend auth, frontend login/dashboard
- [ ] Username / profil qidiruv (ko'p saytda izlash)
- [ ] Email / telefon tekshiruvi
- [ ] Domen / IP / WHOIS razvedka
- [ ] Hisobotlar (report) eksporti

## Ishga tushirish (dev)

**1) Backend + DB (Docker):**
```bash
cp backend/.env.example backend/.env   # keyin SECRET_KEY ni o'zgartiring
docker-compose up -d --build           # yoki: docker compose up -d --build
```

**2) Frontend (lokal, Node 20):**
```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000  (Swagger: http://localhost:8000/docs)

> Eslatma: bu muhitda eski `docker-compose` v1 bor. Kod o'zgargach backendni
> `docker-compose restart backend` bilan yangilang (rebuild v1 da bug beradi).

## Loyiha tuzilishi

```
osint/
├── backend/          FastAPI backend (API, modellar, OSINT yig'uvchilar)
├── frontend/         Next.js frontend
├── docs/             Arxitektura va vazifalar hujjatlari
├── .claude/agents/   Maxsus AI agentlar ta'riflari
├── PROGRESS.md       Bajarilgan ishlar jurnali (sessiyalar orasida)
└── docker-compose.yml
```

## Hujjatlar

- [`PROGRESS.md`](./PROGRESS.md) — bajarilgan ishlar va keyingi qadamlar
- [`docs/architecture.md`](./docs/architecture.md) — arxitektura
- [`docs/tasks.md`](./docs/tasks.md) — vazifalar ro'yxati
