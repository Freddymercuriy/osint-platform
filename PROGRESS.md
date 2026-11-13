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

- [x] **Events → threat intel (Bosqich 6b):**
  - `Feed.kind`: `rss` | `telegram` | `ransomware_live`; `uz_filter` (UZ_KEYWORDS bo'yicha), `ttl` kesh
  - ransomware.live API `/v2/countryvictims/UZ` (rate limit 1/min → 15 daq kesh; .onion havolalar berilmaydi)
  - Telegram ochiq kanallar `t.me/s/<kanal>` (BeautifulSoup parser) — test: kunuzofficial ✅
  - `/api/events?category=` ; frontend tablar: Hammasi / Ransomware / Leak / Telegram / Yangiliklar

- [x] **Telegram user API (Bosqich 6c)** — foydalanuvchining o'z akkaunti orqali (Telethon 1.45):
  - `services/telegram_user.py` — yagona klient, `list_chats()`, `fetch_messages()` (faqat kanal/guruh, shaxsiy chatlar o'qilmaydi;
    yuboruvchi ismi/telefoni saqlanmaydi)
  - `scripts/tg_login.py` — BIR MARTA interaktiv login → `backend/data/tg_session.session` (gitignored!)
  - Feed `kind="telegram_user"` → kategoriyalar `telegram` (kanal) / `tg_group` (guruh); UZ filtr + `TG_EXTRA_KEYWORDS`
  - `GET /api/telegram/status`, `GET /api/telegram/chats`
  - `.env`: TG_API_ID, TG_API_HASH, TG_CHATS, TG_UZ_FILTER, TG_EXTRA_KEYWORDS ... (`env_ignore_empty=True`)
  - Frontend: Events'da TG holat paneli + "TG guruhlar" tabi
  - ✅ Akkaunt ulandi (2026-11-13), 70 chat (41 kanal / 29 guruh) ko'rinadi
  - `TG_CHATS` = 22 ta xavfsizlik/leak chat (foydalanuvchi tasdiqlagan), `TG_LEAK_CHATS` = 9 ta leak chat → "leak" kategoriyasi
  - `TG_MESSAGES_PER_CHAT=100`; birinchi yuklash ~25 s, keyin 5 daq kesh
  - Filtr: `_kw_regex` — UZ o'zaklar prefiks bo'yicha (uzbek→uzbekistan), `TG_EXTRA_KEYWORDS` butun so'z
    (payme≠payment), `.uz` domen chegarasi (day.uz ✓, .uzum ✗). Snippet topilgan joy atrofidan + "🔎 kalit so'zlar"; takror postlar olib tashlanadi
  - ⚠️ `TG_EXTRA_KEYWORDS` ga "leak/db/database" kabi UMUMIY so'z qo'ymang — "YOKI" bilan ulanadi, chet el leaklari to'lib ketadi.
    U yerda faqat O'zbekistonni bildiruvchi nomlar (uzcard, humo, payme, ucell, kapitalbank, viloyatlar...)
  - Test natijasi: 24 ta UZ xabar (masalan Azrael Group: "SYSTEM BREACH — TARGET: day.uz"); leak chatlarning so'nggi 100 xabarida UZ yo'q

- [x] **Fon yig'uvchi + ogohlantirish (Bosqich 7):**
  - `models/event.py` → `events` jadvali (`uid` = sha256(category|source|title|url), unique → takror yozilmaydi; `notified`)
  - `services/events/collector.py` — lifespan'da ishga tushadigan asyncio task, har `EVENTS_POLL_SECONDS` (300) da
    `collect_all()` → yangi yozuvlar → `NOTIFY_CATEGORIES` (leak,ransomware) bo'yicha Telegram **Saved Messages** ga ogohlantirish
    (foydalanuvchining o'z akkaunti `send_message("me")`, bot shart emas)
  - Bootstrap: jadval bo'sh bo'lsa eski yozuvlar uchun ogohlantirilmaydi, faqat "monitoring boshlandi"
  - API: `GET /api/events` endi DB'dan (0.01 s; avval ~25 s), `GET /api/events/status`, `POST /api/events/refresh`
  - Frontend: yig'uvchi holati paneli, "↻ Yangilash", "N tadan M tasi"
  - `DB_ECHO` alohida (avval DEBUG=true SQL bilan loglarni to'ldirardi); `osint.events` logger INFO
  - Test: bootstrap 85 yozuv; refresh → new=0 (dedup ✓); ransomware yozuvini o'chirib qayta topish → ogohlantirish yuborildi, notified=t ✓

- [x] **Saytdagi ogohlantirishlar 🔔 (Bosqich 7b)** — foydalanuvchi talabi: Telegram Saved Messages'ga EMAS, saytga chiqsin
  - `NOTIFY_TELEGRAM=false` (default ham false). Telegram'ga yuborish kodi qoldi, lekin o'chiq
  - `notification_state` jadvali (user_id → seen_at); o'qilmagan = `NOTIFY_CATEGORIES` dagi, `first_seen > seen_at`
  - `GET /api/notifications`, `POST /api/notifications/read`
  - Frontend: `components/NotificationBell.tsx` (har 60 s tekshiradi, qizil hisoblagich, ochiladigan ro'yxat,
    "Hammasini o'qildi", sahifa sarlavhasida "(N)"); `app/dashboard/layout.tsx` — umumiy yuqori panel barcha dashboard sahifalarida

## Foydalanuvchi bergan manbalar holati (2026-11-13 tekshirildi)
| Manba | Holat | Qaror |
|---|---|---|
| ransomware.live | ochiq API | ✅ ulandi |
| Telegram kanallar | ochiq preview | ✅ tayyor — kanal nomlari kutilmoqda |
| intelforums.cc | 200, ochiq | ⏳ ochiq bo'limlar sarlavhalarini UZ filtr bilan kuzatish mumkin (kelishilmagan) |
| breached.st, cracked.st | Cloudflare 403 | ❌ himoyani chetlab o'tmaymiz |
| darkforums.as | JS challenge | ❌ |
| altenens.is, exploit.in | login'ga redirect | ❌ avtomatik login/scrape qilinmaydi |
| reddit | 403/429 | ⏳ rasmiy API (client_id/secret) kerak |

Qoida: leak'larning **o'zi (PII, dumplar) yuklanmaydi/saqlanmaydi** — faqat hodisa metadata (kim, qachon, guruh, manba).

## Jarayonda 🔄

- Foydalanuvchidan: Telegram kanal nomlari; Reddit API kaliti (ixtiyoriy); intelforums bo'yicha qaror.

## Keyingi qadamlar ⏭️

0. (ixtiyoriy) Eski yozuvlarni tozalash (retention), Events sahifasida sahifalash (offset API'da bor)
0. (ixtiyoriy) Ogohlantirish uchun alohida bot / boshqa kanal (email)
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
