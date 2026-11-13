# Arxitektura

## Umumiy ko'rinish

```
┌─────────────┐      HTTP/JSON      ┌──────────────┐      SQL      ┌────────────┐
│  Frontend   │ ──────────────────> │   Backend    │ ────────────> │ PostgreSQL │
│  Next.js    │ <────────────────── │   FastAPI    │ <──────────── │            │
└─────────────┘                     └──────┬───────┘               └────────────┘
                                           │
                                           │ async
                                           v
                                   ┌───────────────────┐
                                   │ OSINT Collectors  │  (tashqi ochiq manbalar)
                                   │ username/domain/..│
                                   └───────────────────┘
```

## Backend qatlamlari (`backend/app/`)

- `main.py` — FastAPI ilovasi, CORS, router'larni ulash
- `core/` — konfiguratsiya (`config.py`), xavfsizlik (`security.py`), DB ulanish (`db.py`)
- `models/` — SQLAlchemy modellari (User, SearchJob, Result, ...)
- `api/` — endpoint'lar (routerlar): `auth.py`, `search.py`, ...
- `services/collectors/` — OSINT yig'uvchilar. Har biri umumiy `BaseCollector` interfeysiga amal qiladi.

### Collector interfeysi

Har bir OSINT moduli (`UsernameCollector`, `DomainCollector`, ...) bir xil shaklga ega:

```python
class BaseCollector:
    name: str
    async def run(self, query: str) -> list[CollectResult]: ...
```

Bu yangi modul qo'shishni oson qiladi — faqat yangi collector yozib, ro'yxatga qo'shiladi.

## Frontend (`frontend/`)

- Next.js App Router
- `app/` — sahifalar (login, dashboard, search)
- `lib/api.ts` — backend bilan ishlash (fetch wrapper)
- Tailwind CSS

## Autentifikatsiya

- JWT token (backend beradi), frontend `localStorage`/cookie da saqlaydi.
- Parollar `bcrypt`/`argon2` bilan hash qilinadi.

## Xavfsizlik & axloq

- Rate limiting (tashqi manbalarni ortiqcha yuklamaslik uchun).
- Faqat ochiq (public) ma'lumotlar yig'iladi.
- Maxfiy kalitlar `.env` da, hech qachon git'ga tushmaydi.
