# PROGRESS — Bajarilgan ishlar jurnali

> Bu fayl har sessiyada ishni tez davom ettirish uchun. Yangi sessiya boshlanganda **avval shu faylni o'qing**, so'ng `docs/tasks.md` ni ko'ring.

## Hozirgi holat

**Bosqich:** 6 — Events (O'zbekiston yangiliklari) skeleti tayyor → foydalanuvchi saytlar ro'yxatini kutyapmiz
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
- [x] **Email / telefon modullari (Bosqich 5):**
  - `Result` modeliga `detail` ustuni qo'shildi (CollectResult, schema ham)
  - `EmailCollector`: sintaksis (email-validator), MX (dns.asyncresolver), Gravatar (md5 avatar)
  - `PhoneCollector`: `phonenumbers` — yaroqlilik, format, davlat, operator, tur, vaqt mintaqasi (offline)
  - `/api/search/email`, `/api/search/phone` endpointlar (`_run_and_save` umumiy yordamchi)
  - Frontend: umumiy `components/SearchModule.tsx`; `/dashboard/email`, `/dashboard/phone`,
    `/dashboard/username` (barchasi shu komponentni ishlatadi, `detail` ko'rsatiladi)
  - Test: email torvalds@linux.com → MX topildi; telefon +998901234567 → Uzbekistan/Beeline/Mobil ✅

- [x] **Events moduli skeleti (Bosqich 6):**
  - `services/events/feeds.py` — manbalar ro'yxati (`Feed` dataclass). Hozir seed: Gazeta.uz (UZ/RU), Kun.uz (UZ) — ishlaydi
  - `services/events/aggregator.py` — RSS'larni async yig'adi (httpx + feedparser), kalit so'z filtri, sanasi bo'yicha saralash
  - `GET /api/events?limit=&q=` endpoint
  - Frontend: `/dashboard/events` (kartalar, "N soat oldin", filtr)

## Jarayonda 🔄

- Foydalanuvchi O'zbekiston **news saytlar** va **reg (login) saytlar** ro'yxatini beradi.
  - News → `feeds.py` ga qo'shish (RSS topish; RSS yo'q bo'lsa alohida HTML parser)
  - Reg saytlar → ⚠️ ToS masalasi; foydalanuvchidan ruxsat/o'z hisobi borligini tasdiqlash so'raldi.
    Ruxsat bo'lmasa scrape qilinmaydi.

## Keyingi qadamlar ⏭️

0. Saytlar ro'yxati kelgach: feedlarni qo'shish, test, push
1. Domen / IP / WHOIS collector moduli
2. Qidiruv tarixini frontend'da ko'rsatish sahifasi (`/api/search/history`, `/jobs/{id}` bor)
3. Collector'larni `name` bo'yicha registry orqali ulash
4. (keyin) Alembic migratsiyalar — hozir dev'da `create_all` (sxema o'zgarsa jadvalni DROP qilib qayta yaratish kerak)
5. (keyin) Next 15 ga ko'chish — npm audit ogohlantirishlari uchun

## Yangi dep eslatmasi ⚠️
- `phonenumbers` requirements.txt da bor, lekin hozir faqat konteynerga `pip install` bilan
  qo'shilgan (v1 rebuild bug'i sabab). To'liq rebuild bo'lsa avtomatik o'rnatiladi.

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
