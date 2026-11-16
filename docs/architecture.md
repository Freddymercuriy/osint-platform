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

Mavjud collectorlar: `username` (faqat Telegram — `telegram_account.py`: akkaunt, username tarixi, umumiy guruhlar), `email`, `phone`, `domain` (domen yoki IP). Har biri `POST /api/search/<kind>` orqali
chaqiriladi; natija `search_jobs` + `results` jadvallariga yoziladi (tarix: `GET /api/search/history`, tur bo'yicha sonlar `GET /api/search/history/counts`, `GET|DELETE /api/search/jobs/{id}`; hisobot: `GET /api/search/jobs/{id}/export` →
JSON fayl yoki `/report/{id}` chop etish sahifasi orqali PDF).

`DomainCollector` qoidalari: foydalanuvchi kiritgan host'ga to'g'ridan-to'g'ri ulanmaydi (SSRF) — faqat DNS so'rovlari va
qat'iy belgilangan ochiq xizmatlar (rdap.org, crt.sh, WHOIS serverlari); WHOIS/RDAP'dagi shaxsiy ma'lumotlar
(registrant ismi, email, telefon, manzil) o'qilmaydi va saqlanmaydi.

## Events: manbalar, yig'uvchi, hodisalar (v2)

```
sources (bazada, admin CRUD)          categories (15 ta, en/ru/uz)
     │  har biri o'z jadvali                │
     v                                      │
scheduler (API jarayoni ichida, advisory lock, ≤8 parallel, xost navbati)
     │  connectors/<kind>.py  →  RawItem[]
     v
filters (hudud / mavzu / chet el)  →  pipeline (URL, muddat, baseline, takror → also_reported_by)  →  events
     │                                                                                                  │
     └── source_runs (har urinish, 30 kun) + sources sog'liq maydonlari                                  └── 🔔, API, statistika
```

- **`sources`** — runtime'dagi yagona manbalar ro'yxati (`config` JSONB, til, qat'iy kategoriya, scope, filtrlar,
  `translate`, interval/jitter/backfill, kalit o'zgaruvchisining NOMI, ETag/Last-Modified, `next_run_at`, kursor `state`,
  sog'liq: status, oxirgi tekshiruv/muvaffaqiyat/xato/HTTP/kechikish, ketma-ket xatolar, elementlar soni).
  Holatlar: `ok` · `degraded` · `down` · `blocked` · `auth_missing` · `disabled` · `never_run`.
- **`services/events/scheduler.py`** — rejalashtiruvchi: `next_run_at = now + interval × random(1 ± jitter)`, xatoda
  eksponensial backoff (≤ 6 soat, Retry-After / FloodWait), PostgreSQL advisory lock bilan yagona nusxa.
- **`services/connectors/`** — ulagichlar, tur bo'yicha ro'yxatga olinadi (`@register`); yozish qoidalari:
  [`docs/connectors.md`](connectors.md). `http.py` — xost navbati va pauzalar, shartli so'rov, holat kodlari, SSRF.
- **`services/events/pipeline.py`** — bazaga yozish: http(s) havolalar, `EVENTS_SINCE` va kategoriya muddati, baseline
  (birinchi yig'ish ogohlantirmaydi), takrorlar mavjud hodisaning `also_reported_by` ga qo'shiladi.
- Kalit so'zlar va regexlar kodda: `services/events/feeds.py` (hudud, mavzu, chet el belgilari), `dedup.py`, `geo.py`.
- Kategoriyalar: `categories` (15 ta, en/ru/uz, jiddiylik, rang, ikon, notify, saqlash muddati, `rules`) —
  `services/events/classifier.py` (manba → ulagich → qoidalar → `other`), `categories.py` (qayta tasniflash).
- Tarjima: `event_translations` (en/ru/uz), `services/i18n/` — til aniqlash, o'zbek kirill→lotin, shablon sarlavhalar,
  Google Cloud Translation navbati (kesh, oylik chegara, qayta urinish).
- Hodisalar: `GET /api/events` — filtrlar birlashadi (AND): `category`, `severity`, `country`, `channel`, `source`,
  `scope`, `source_lang`, `q`, davr: `range=24h|7d|30d|90d` (hozirdan orqaga, soat aniqligida) yoki `date_from`/`date_to`
  (Toshkent kuni; berilsa `range` e'tiborsiz — statistika bilan bir xil qoida).
- Statistika: `api/stats_v2.py` — `/api/stats/kpis|timeseries|breakdown|heatmap|source-health|latest`, hammasi
  `/api/events` filtrlari bilan, vaqt bo'laklari `APP_TIMEZONE` da.
- Admin API: `/api/admin/sources` (CRUD, test, run, runs, export/import), `/api/admin/collector`,
  `/api/admin/categories` (CRUD, reorder, reclassify), `/api/admin/translations`, `/api/admin/users`;
  adminlar uchun tizim ogohlantirishlari (`admin_alerts`, uzoq ishlamayotgan manba).
- Xatolar: `core/errors.py` — `{"detail": <tarjima>, "code": ...}` (`core/i18n.py`, `Accept-Language`);
  rate limiting: `core/ratelimit.py` (login, tekshiruvlar, qo'lda yig'ish; jarayon xotirasida). Proxy ortida:
  `TRUSTED_PROXIES` (IP/CIDR) — faqat shulardan kelgan so'rovda `X-Forwarded-For` o'qiladi (o'ngdan birinchi ishonchsiz
  manzil = mijoz); bo'sh bo'lsa sarlavha e'tiborsiz (soxtalashtirib bo'lmaydi).
- Rollar: `admin` (manbalar, kategoriyalar, yig'uvchi, Telegram) va `analyst`.
- Sxema: Alembic (`backend/migrations/`), konteyner ishga tushganda `scripts/migrate.py` → `upgrade head`.

## Frontend (`frontend/`)

- Dizayn: [`docs/design-system.md`](design-system.md) — semantik tokenlar (Light/Dark/System, `next-themes`),
  `next-intl` (uz/ru/en, cookie `NEXT_LOCALE` + `users.locale`, `messages/*.json`), `lib/format.ts`.
- Next.js App Router
- `app/` — sahifalar (login, dashboard, search)
- `lib/api.ts` — backend bilan ishlash (fetch wrapper)
- `lib/modules.ts` — tekshiruv modullari ro'yxati (nom, rang, ikon, yo'l)
- `components/SearchModule.tsx` — barcha qidiruv sahifalari uchun umumiy komponent
- `scripts/qa/` — UI smoke-test (headless Chrome)
- Tailwind CSS

## Autentifikatsiya

- JWT (PyJWT, HS256) — frontend `localStorage` da saqlaydi; parollar `bcrypt` bilan.
- Rollar: `admin` (`ADMIN_EMAILS` yoki eng eski foydalanuvchi) va `analyst`; `require_admin` — barcha `/api/admin/*`,
  `/api/telegram/*`, `POST /api/events/refresh`, `PATCH /api/events/{id}`. `REGISTRATION_OPEN`; production'da standart
  `SECRET_KEY` bilan backend ishga tushmaydi.

## Xavfsizlik & axloq

- Rate limiting: login (IP va email bo'yicha), tekshiruvlar, qo'lda yig'ish — 429 + `Retry-After`.
- Tashqi manbalarga: xost bo'yicha navbat va pauza, jadval jitter bilan, backoff, `Retry-After` hurmati.
- SSRF: manba so'rovlari (redirect'lar ham) xususiy/loopback/link-local manzillarga yuborilmaydi.
- Faqat ochiq (public) ma'lumotlar yig'iladi.
- Maxfiy kalitlar `.env` da, hech qachon git'ga tushmaydi.
