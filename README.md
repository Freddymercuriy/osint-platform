# OSINT Platform

Markaziy Osiyo (O'zbekiston, Qozog'iston, Qirg'iziston, Tojikiston, Turkmaniston) uchun ochiq manbalar razvedkasi va
kibertahdidlar monitoringi: ransomware qurbonlari, ma'lumotlar sizib chiqishi, fishing, zaifliklar va boshqa kiber
hodisalar lentasi, statistika dashboard'i, hamda Telegram username / email / telefon / domen tekshiruvlari.

> ⚠️ **Faqat qonuniy va axloqiy maqsadlar uchun.** Platforma faqat ochiq sahifalar, lentalar va rasmiy API'lardan
> metadata yig'adi (kim, nima, qachon, qaysi guruh, havola). Login devori, CAPTCHA yoki Cloudflare tekshiruvi chetlab
> o'tilmaydi — bunday manba "blocked" deb belgilanadi. Sizib chiqqan fayllar, parollar va shaxsiy ma'lumotlar yuklanmaydi
> va saqlanmaydi.

## Texnologiyalar

| Qatlam | Texnologiya |
|--------|-------------|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind, next-themes (Light/Dark/System), next-intl (uz/uz-Cyrl/ru/en), Apache ECharts |
| Backend | Python 3.12 + FastAPI, SQLAlchemy (async), Alembic, Telethon, httpx |
| Database | PostgreSQL 16 |
| Infra | Docker Compose (Redis/Celery yo'q — yig'uvchi API jarayoni ichida, asyncio + PostgreSQL advisory lock) |

## Imkoniyatlar

- **Hodisalar lentasi** — ~100 manba (RSS, Google News, ransomware.live, RansomLook, HIBP, CISA KEV, URLhaus, ThreatFox,
  OpenPhish, OTX, Cloudflare Radar, milliy CERT'lar, Telegram kanal/guruhlari); har manba o'z tasodifiy jadvali bilan,
  sog'liq holati, backoff, baseline; takrorlar birlashtiriladi ("N ta manba xabar qildi"); 15 mavzu kategoriyasi
  (qoidalar admin panelida); har hodisa en/ru/uz (o'z NLLB tarjima servisi, `TRANSLATE_API_URL`).
- **Filtrlar** — kategoriya, jiddiylik, davlat, kanal, manba, qamrov (mintaqa/global), asl til, sana, matn — URL'da.
- **Dashboard** — KPI (oldingi davrga nisbatan), vaqt bo'yicha, kategoriyalar, davlatlar, jiddiylik trendi, hafta×soat,
  manbalar, ransomware guruhlari, sohalar, so'nggi muhim hodisalar, manbalar sog'lig'i; kesishma filtr, jadval, CSV.
- **Tekshiruvlar** — Telegram username/ID, email, telefon, domen/IP/WHOIS; tarix va hisobot (JSON / PDF).
- **Admin** — manbalar (CRUD, sinash, hozir yig'ish, tarix, eksport/import), kategoriyalar (qoidalar, qayta tasniflash),
  tizim (yig'uvchi, tarjima, Telegram, foydalanuvchilar). Rollar: `admin`, `analyst`.

## Ishga tushirish (dev)

**1) Hammasi Docker'da (DB + backend + frontend production build + Tor proksi):**
```bash
cp backend/.env.example backend/.env
# backend/.env: SECRET_KEY (python -c 'import secrets; print(secrets.token_hex(32))'), ADMIN_EMAILS, kalitlar (pastda)
# ixtiyoriy: loyiha ildizidagi .env da NEXT_PUBLIC_API_URL=... (frontend build'iga yoziladi; bo'sh = host:8000)
docker-compose up -d --build           # yoki: docker compose up -d --build
```
Backend konteyneri ishga tushganda migratsiyalarni o'zi qo'llaydi (`scripts/start.sh` → `alembic upgrade head`).
Konteynerlarda `restart: unless-stopped` — kompyuter qayta yoqilganda o'zi ko'tariladi.
`tor` xizmati — faqat `.onion` manbalar (`onion_feed`) uchun SOCKS proksi; hostga port ochmaydi.

**2) Frontend'ni ishlab chiqish rejimida (hot reload, Node 20):**
```bash
docker-compose stop frontend           # 3000-port bo'shasin
cd frontend
cp .env.example .env.local
npm install
npm run dev                            # tugagach: docker-compose start frontend
```

- Frontend: http://localhost:3000 · Backend API: http://localhost:8000 (Swagger: `/docs`)
- LAN'dan (boshqa kompyuter/telefon): frontend va backend `0.0.0.0` da (compose: `0.0.0.0:3000`, `0.0.0.0:8000`;
  `next dev -H 0.0.0.0`), PostgreSQL — faqat `127.0.0.1`. `NEXT_PUBLIC_API_URL` bo'sh (API sahifa ochilgan host'ning
  8000-portiga ergashadi) va `backend/.env` da `CORS_ALLOW_LAN=true` (ichki tarmoqdagi istalgan manzil :3000).
  Faqat shu kompyuterdan kerak bo'lsa — compose'da `127.0.0.1:PORT:PORT` (Docker portlari ufw'ni chetlab o'tadi).
- Birinchi ro'yxatdan o'tgan foydalanuvchi (yoki `ADMIN_EMAILS` dagilar) — admin. Ro'yxatdan o'tish
  `ENVIRONMENT=development` da ochiq, boshqa muhitda `REGISTRATION_OPEN=true` kerak.
- Telegram (ixtiyoriy): `TG_API_ID`, `TG_API_HASH` va bir marta login —
  `docker-compose exec backend python scripts/tg_login.py`.
- Tarjima: o'z NLLB servisimiz, kalit kerak emas — `TRANSLATE_API_URL` (standart `https://translate.deepcore.uz`),
  `TRANSLATE_TIMEOUT_SECONDS=90`; o'chirish — `TRANSLATE_ENABLED=false`. Holati: admin → Tizim → Tarjima.
  O'zbek kirill (`uzn_Cyrl`) — lotin tarjimadan [latin.jaybi.uz](https://latin.jaybi.uz) dvigateli bilan
  (`backend/app/services/i18n/vendor/`, MIT).
- Hodisa rasmlari (16:9; dashboard kartalari va Telegram postlari): maqolaning o'z rasmi (RSS media / og:image)
  yoki platforma chizgan illyustratsiya — tashqi servis va kalit kerak emas. Fayllar `backend/media/`
  (`MEDIA_DIR`, git'da yo'q); `MEDIA_SOURCE_IMAGES=false` — faqat illyustratsiya; `MEDIA_ENABLED=false` — fon
  ishchisi o'chiq (rasm so'ralganda baribir chiziladi). Kanal postlari rasm bilan: `PUBLISHER_PHOTOS=true`,
  maqola rasmini kutish `PUBLISHER_IMAGE_WAIT_MINUTES=3`.

- Reverse proxy (nginx, Caddy...) ortida ishlatilsa: `TRUSTED_PROXIES` ga proxy manzilini yozing (IP/CIDR) —
  aks holda login limiti hamma foydalanuvchini bitta proxy IP'si deb hisoblaydi. Rate limit va yig'uvchi bitta
  uvicorn jarayoni uchun mo'ljallangan (bir nechta worker ishlatilmaydi).

> Eslatma: bu kompyuterda eski `docker-compose` v1. Kod o'zgargach: `docker-compose restart backend`
> (`--reload` yo'q). `.env` dagi yangi kalitlar uchun konteynerni qayta yarating (PROGRESS.md → Docker eslatmasi).

### Tashqi kalitlar (`backend/.env`; bo'sh bo'lsa manba "auth_missing" holatida o'chiq turadi)

| O'zgaruvchi | Nima uchun |
|---|---|
| `RANSOMWARE_LIVE_API_KEY` | ransomware.live PRO API (bepul shaxsiy kalit) |
| `ABUSECH_AUTH_KEY` | URLhaus va ThreatFox |
| `OTX_API_KEY` | LevelBlue (AlienVault) OTX |
| `NVD_API_KEY` | NVD (ixtiyoriy, limitni oshiradi; manba standart o'chiq) |
| `CLOUDFLARE_API_TOKEN` | Cloudflare Radar (ixtiyoriy) |

Kalit qo'shilgach: backendni qayta yarating va admin panelda (Manbalar) manbani yoqing.

## Migratsiyalar

```bash
docker-compose exec backend python scripts/migrate.py               # upgrade head (start'da avtomatik)
docker-compose exec backend python scripts/migrate.py downgrade -1  # bitta qadam orqaga
```
- Alembic'dan oldingi (v1) baza avtomatik `0001_baseline` ga "stamp" qilinadi — jadvallar qayta yaratilmaydi.
- Har migratsiyada `downgrade` bor; test `base ↔ head` ni vaqtinchalik bazada sinaydi. Qo'llashdan oldin nusxa:
  `docker-compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > ~/osint-backups/<nom>.sql`.

## Testlar

```bash
docker-compose exec backend pytest                 # backend (alohida test bazasi, tarmoqsiz)
cd frontend && npx tsc --noEmit && npm run test:i18n && npm run test:contrast
NEXT_DIST_DIR=.next-build npm run build            # production build (dev serverni buzmaydi)
TOKEN=$(docker-compose exec -T backend python scripts/qa_token.py --role admin) MATRIX=1 node scripts/qa/smoke.js
```

## Loyiha tuzilishi

```
osint/
├── backend/          FastAPI: api/, core/ (config, i18n, errors, ratelimit), models/, services/ (connectors/, events/,
│                     i18n/, collectors/), migrations/ (Alembic), scripts/, tests/
├── frontend/         Next.js: app/, components/, lib/, messages/ (uz/uz-Cyrl/ru/en), scripts/ (qa, i18n, kontrast)
├── docs/             Arxitektura, dizayn tizimi, ulagichlar, vazifalar, v2 spetsifikatsiyasi
├── .claude/agents/   AI agentlar ta'riflari
├── PROGRESS.md       Bajarilgan ishlar jurnali (sessiyalar orasida)
└── docker-compose.yml
```

## Hujjatlar

- [`PROGRESS.md`](./PROGRESS.md) — bajarilgan ishlar, tekshirilgan / tekshirilmagan, davom ettirish nuqtasi
- [`docs/architecture.md`](./docs/architecture.md) — arxitektura
- [`docs/design-system.md`](./docs/design-system.md) — tokenlar, temalar, tillar, grafiklar
- [`docs/connectors.md`](./docs/connectors.md) — yangi manba ulagichini yozish
- [`docs/tasks.md`](./docs/tasks.md) — vazifalar ro'yxati
- [`docs/upgrade-v2-spec.md`](./docs/upgrade-v2-spec.md) — v2 yangilanish spetsifikatsiyasi
