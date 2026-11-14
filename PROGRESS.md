# PROGRESS — Bajarilgan ishlar jurnali

> Bu fayl har sessiyada ishni tez davom ettirish uchun. Yangi sessiya boshlanganda **avval shu faylni o'qing**, so'ng `docs/tasks.md` ni ko'ring.

## Hozirgi holat

**Bosqich:** 10 — Domen / IP / WHOIS moduli va Qidiruv tarixi sahifasi qo'shildi; Bosqich 9 (motion design) tekshiruvlari yopildi
**Oxirgi yangilanish:** 2026-11-14

## ▶️ DAVOM ETISH UCHUN

### Ishga tushirish (shu kompyuterda)
```bash
docker-compose start                      # db + backend (konteynerlar mavjud bo'lsa); bo'lmasa: docker-compose up -d
cd frontend && npm run dev                # http://localhost:3000
# backend kodi o'zgarsa: docker-compose restart backend  (uvicorn --reload yo'q)
```

### Boshqa kompyuterda ishga tushirish
Git'da **yo'q** narsalar (qo'lda ko'chirish yoki qayta yaratish kerak):
| Nima | Qayerda | Nima qilish |
|---|---|---|
| `backend/.env` | maxfiy | nusxalash, yoki `cp backend/.env.example backend/.env` va to'ldirish: `SECRET_KEY` (yangi random), `TG_API_ID`, `TG_API_HASH`, `TG_CHATS`, `TG_LEAK_CHATS`, `TG_EXTRA_KEYWORDS`, `TG_MESSAGES_PER_CHAT=100`, `NOTIFY_TELEGRAM=false` |
| `backend/data/tg_session.session` | Telegram sessiyasi | nusxalash YOKI qayta login: `docker-compose exec backend python scripts/tg_login.py` |
| Postgres ma'lumotlari | docker volume | ko'chmaydi: foydalanuvchi qayta ro'yxatdan o'tadi, hodisalarni fon yig'uvchi 5 daqiqada o'zi yig'adi |
| `frontend/.env.local` | — | `cp frontend/.env.example frontend/.env.local` |

```bash
git clone https://github.com/Freddymercuriy/osint-platform && cd osint-platform   # yoki: git pull
# backend/.env ni joylashtiring, keyin:
docker-compose build backend && docker-compose up -d        # yoki: docker compose ...
cd frontend && npm install && cp .env.example .env.local && npm run dev   # http://localhost:3000
```
Push uchun `gh auth login` kerak. Claude'ga: "PROGRESS.md ni o'qib, davom et" deyish yetarli.

### 2026-11-14 sessiyasida qilingan (Bosqich 9 yopildi + Bosqich 10)
- **Kechagi ⚠️ tekshiruvlar bajarildi:** qidiruv sahifalari (natija kartalari, filtr almashishi — username/phone), register,
  mobil 360px, framer-motion bilan production build — hammasi o'tdi. Topilgan va tuzatilgan kamchiliklar:
  - mobil dashboard: KPI yorlig'i ikonka ustiga chiqardi → `StatTile` ga `stacked` prop (tor to'rda ikonka yorliq ustida);
  - mobil "Muhim hodisalar": sarlavha 3-4 harfga qisilardi → nishon + vaqt birinchi qatorda, sarlavha to'liq kenglikda;
  - sanalar `2026 M09 22` ko'rinishida chiqardi (brauzerda `uz-UZ` lokali to'liq emas) → `formatDate` / `formatTime` /
    `formatDateTime` (`components/ui`, o'zbekcha oy nomlari). **`toLocaleDateString("uz-UZ")` ishlatmang**;
  - `favicon.ico` 404 → `app/icon.svg`.
- **Domen / IP / WHOIS moduli** (`/dashboard/domain`, `POST /api/search/domain`): `services/collectors/domain.py` —
  - domen: DNS A/AAAA, NS, MX, SPF, DMARC; WHOIS/RDAP (rdap.org → rasmiy RDAP; ishlamasa port 43 WHOIS, serverni IANA'dan oladi;
    .uz ham ishlaydi); domen muddati (30 kundan kam qolsa ogohlantirish); subdomenlar (crt.sh, Certificate Transparency);
    hosting/ASN (Team Cymru DNS);
  - IP (v4/v6): PTR, ASN, RDAP tarmoq; xususiy/loopback manzillarga tashqi so'rov yuborilmaydi;
  - **maxfiylik:** WHOIS/RDAP'dan registrant/admin/tech ismi, email, telefon, manzil o'qilmaydi va saqlanmaydi — faqat
    registrator, sanalar, holat, NS. **SSRF:** foydalanuvchi kiritgan host'ga hech qachon to'g'ridan-to'g'ri ulanilmaydi
    (faqat DNS, rdap.org, crt.sh, WHOIS serverlari); kirish regex bilan tekshiriladi;
  - ⚠️ crt.sh tez-tez sekin/502 → o'sha qator "Noaniq" chiqadi va qidiruv ~12 s davom etadi (qolgan qatorlar ishlayveradi).
- **Qidiruv tarixi** (`/dashboard/history`): modul bo'yicha filtr (sanoq bilan), matn bo'yicha qidiruv (server tomonda, debounce),
  natijalarni qator ichida ochish, "Qayta" (modul sahifasiga `?q=` bilan — so'rov oldindan to'ldiriladi), bitta yozuvni o'chirish
  va tarixni tozalash (ikki bosqichli tasdiq), "Yana yuklash".
  API: `GET /api/search/history?kind=&q=&limit=&offset=` (har yozuvda `checked`/`found`), `DELETE /api/search/jobs/{id}`,
  `DELETE /api/search/history?kind=`. Natijalar DB ustun uzunligiga kesiladi (`_clip`).
- `lib/modules.ts` — modullar ro'yxati (nom/rang/ikon) bitta joyda: dashboard, tarix, sidebar shundan oladi.
- `SearchModule` natija kartasi: manba nomi 2 qatorgacha, uzun izoh bosilganda to'liq ochiladi.
- **UI smoke-test repoda:** `frontend/scripts/qa/` (headless Chrome + CDP, qo'shimcha paket shart emas):
  `cd frontend && TOKEN=<JWT> node scripts/qa/smoke.js` — 10 sahifa × desktop/mobil: konsol xatolari, gorizontal skroll,
  ko'rinmay qolgan kontent; skrinshotlar `frontend/.qa-shots/` (gitignored).
- Agentlar ishlatildi: `osint-collector` (domain.py), `frontend` (history sahifasi); qolgani va ko'rib chiqish — asosiy sessiyada.

### Tekshirilgan / tekshirilMAGAN
- ✅ `npx tsc --noEmit`; `NEXT_DIST_DIR=.next-build npm run build` (12 route); smoke-test 20/20 toza (konsol xatosiz).
- ✅ API jonli sinovi: domen (`kun.uz`, `gov.uz`), IP (`8.8.8.8`), yaroqsiz kirish → 422, tokensiz → 401, tarix filtri/sahifalash,
  o'chirish (204 → 404, natijalar CASCADE bilan ketadi), boshqa foydalanuvchi begona yozuvni ko'rmaydi/o'chira olmaydi (404).
- ✅ Brauzerda: domen qidiruvi (skan → natija), `?q=` oldindan to'ldirish, tarix filtri/qidiruvi/ochish, o'chirish (bekor + tasdiq).
- ⚠️ **Tekshirilmadi:** "Tarixni tozalash" tugmasining tasdiq yo'li brauzerda (test hisobining tarixini o'chirmaslik uchun; API'ning o'zi
  sinalgan); WHOIS port-43 parseri faqat `.uz` da sinalgan (boshqa ccTLD formatlari tanilmasa qator "Noaniq" bo'ladi);
  `next lint` (ESLint sozlanmagan).

### Keyingi qadamlar (tartib bilan)
1. Foydalanuvchi UI'ni ko'rib fikr bildiradi → sayqallash (animatsiya tezligi/kuchi, ranglar).
2. Hisobot eksporti (qidiruv natijasi → JSON/PDF) — tarix sahifasidan.
3. Events: sahifalash (API'da `offset` bor), eski hodisalarni tozalash (retention);
   intelforums.cc ochiq bo'limlari (foydalanuvchi qarori kutilmoqda), Reddit (API kaliti kerak), ARADA SPY chatlarini `TG_CHATS` ga qo'shish.
4. Domen moduli: crt.sh o'rniga/yoniga tezroq CT manbasi; natijalarni qisqa muddat keshlash.
5. Texnik qarz: Alembic migratsiyalar; pytest to'plami (hozir API testlari qo'lda); Next 15+ ga ko'chish (npm audit: 2 ta ogohlantirish);
   test hisobi `test@example.com / password123` ni o'chirish (hozir QA uchun ishlatiladi); rate limiting (qidiruv endpointlari).

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

- [x] **UI to'liq qayta dizayn (Bosqich 8)** — foydalanuvchi: "platforma yomon chiqqan, wow bo'lsin"
  - Agentlar 5 → 9: `ui-designer`, `qa-tester`, `security-auditor`, `docs-writer` qo'shildi (`.claude/agents/`)
    ⚠️ Bu sessiyada `.claude/agents` dagi turlar Agent tool'da ro'yxatda yo'q edi → `general-purpose` agentlarga
    rol faylini o'qish buyurildi. Yangi sessiyada ular to'g'ridan-to'g'ri mavjud bo'lishi mumkin.
  - Dizayn tizimi: `docs/design-system.md` (uslub, ranglar, qoidalar), `tailwind.config.ts` (ink/brand ranglar, animatsiyalar),
    `globals.css` (kiber-to'r fon, `.glass`, `.text-gradient`...), `components/ui/index.tsx` (Card, Button, Input, Badge,
    CategoryBadge, StatusBadge, IconBox, PageHeader, StatTile, EmptyState, ErrorBanner, Skeleton, LiveDot, Logo, timeAgo),
    `lib/categories.ts` (kategoriya nom/rang/ikon), shriftlar Inter + JetBrains Mono, ikonlar `lucide-react`
  - Qobiq: `app/dashboard/layout.tsx` + `components/shell/Sidebar.tsx` (bo'limlar, tizim holati, foydalanuvchi) + yuqori panel (🔔)
  - Dashboard: hero + radar, 5 KPI, kunlik ustunli grafik (+jadval ko'rinishi), kategoriyalar, muhim hodisalar, faol manbalar, modullar.
    Grafik rangi `#3987e5` dataviz validatoridan o'tgan (navy fonda ham). `components/charts/{ColumnChart,HBarList}.tsx`
  - Backend: `GET /api/stats/overview` (kunlik taqsimot, kategoriyalar, top manbalar, muhim hodisalar, qidiruvlar)
  - Agentlar qilgan: landing + login/register (agent A), SearchModule + username/email/phone (agent B), Events vaqt chizig'i (agent C)
  - Tuzatishlar: HTML entity'lar (`&nbsp;`) — `_unescape()` + bazadagi 39 yozuv tozalandi (uid qayta hisoblandi, takror 0);
    TG akkaunt yorlig'ida `(@None)`; sidebar yorlig'i sig'masligi
  - Tekshiruv: headless Chrome (CDP) skrinshotlari — landing, login, dashboard, events, username (skan + natija) ✅

- [x] **Domen / IP / WHOIS + Qidiruv tarixi (Bosqich 10, 2026-11-14)** — tafsilotlar yuqorida ("2026-11-14 sessiyasida qilingan")

## ⚠️ Docker eslatmasi (muhim)
- `docker-compose.yml` dagi `env_file` qiymatlari konteyner **yaratilganda** muhrlanadi. `.env` dagi MAVJUD kalitni o'zgartirsangiz
  (masalan CORS_ORIGINS), `restart` yetmaydi → konteynerni qayta yaratish kerak:
  `docker-compose build backend && docker-compose stop backend && docker-compose rm -f backend && docker-compose up -d backend`
  (avval `rm` qilish v1 dagi `ContainerConfig` bug'ini chetlab o'tadi). Ma'lumotlar (postgres volume, backend/data) saqlanadi.
- 2026-11-13: image qayta qurildi — barcha paketlar (phonenumbers, feedparser, bs4, telethon) endi image ichida.
- `CORS_ORIGINS` ga `http://localhost:3001` qo'shilgan (skrinshot uchun alohida prod server).
- Frontend `npm run build` foydalanuvchining ishlab turgan `npm run dev` (3000) ni buzadi (.next almashadi) → dev'ni qayta ishga tushirish kerak.

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

Yuqoridagi "Keyingi qadamlar (tartib bilan)" bo'limiga qarang. Qo'shimcha (ixtiyoriy):
- Ogohlantirish uchun alohida bot / boshqa kanal (email)
- Collector'larni `name` bo'yicha registry orqali ulash

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
