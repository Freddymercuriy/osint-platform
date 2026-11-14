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

Mavjud collectorlar: `username`, `email`, `phone`, `domain` (domen yoki IP). Har biri `POST /api/search/<kind>` orqali
chaqiriladi; natija `search_jobs` + `results` jadvallariga yoziladi (tarix: `GET /api/search/history`, `GET|DELETE /api/search/jobs/{id}`).

`DomainCollector` qoidalari: foydalanuvchi kiritgan host'ga to'g'ridan-to'g'ri ulanmaydi (SSRF) — faqat DNS so'rovlari va
qat'iy belgilangan ochiq xizmatlar (rdap.org, crt.sh, WHOIS serverlari); WHOIS/RDAP'dagi shaxsiy ma'lumotlar
(registrant ismi, email, telefon, manzil) o'qilmaydi va saqlanmaydi.

## Frontend (`frontend/`)

- Next.js App Router
- `app/` — sahifalar (login, dashboard, search)
- `lib/api.ts` — backend bilan ishlash (fetch wrapper)
- `lib/modules.ts` — tekshiruv modullari ro'yxati (nom, rang, ikon, yo'l)
- `components/SearchModule.tsx` — barcha qidiruv sahifalari uchun umumiy komponent
- `scripts/qa/` — UI smoke-test (headless Chrome)
- Tailwind CSS

## Autentifikatsiya

- JWT token (backend beradi), frontend `localStorage`/cookie da saqlaydi.
- Parollar `bcrypt`/`argon2` bilan hash qilinadi.

## Xavfsizlik & axloq

- Rate limiting (tashqi manbalarni ortiqcha yuklamaslik uchun).
- Faqat ochiq (public) ma'lumotlar yig'iladi.
- Maxfiy kalitlar `.env` da, hech qachon git'ga tushmaydi.
