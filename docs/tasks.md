# Vazifalar ro'yxati

Belgilar: ✅ bajarildi · 🔄 jarayonda · ⬜ kutilmoqda

## Bosqich 1 — Skelet
- ✅ Git repo, `.gitignore`, `README.md`
- ✅ Hujjatlar (`PROGRESS.md`, `docs/`)
- ✅ Agent ta'riflari (`.claude/agents/`)
- ✅ GitHub repo + birinchi push

## Bosqich 2 — Backend asos ✅
- ✅ FastAPI ilova (`main.py`), sozlamalar (`config.py`)
- ✅ PostgreSQL ulanish (SQLAlchemy async), `.env.example`
- ✅ User modeli (migratsiya o'rniga hozir dev'da `create_all`; Alembic keyin)
- ✅ Auth: ro'yxatdan o'tish, login, JWT, `/me`
- ✅ `/health` va `/docs` ishlaydi (Docker'da test qilindi)

## Bosqich 3 — Frontend asos ✅
- ✅ Next.js + Tailwind sozlash
- ✅ API client (`lib/api.ts`)
- ✅ Login / register sahifalari
- ✅ Dashboard layout (sidebar, header)

## Bosqich 4 — Username qidiruv moduli ✅
- ✅ `UsernameCollector` (13 saytda profil tekshirish, async)
- ✅ `/api/search/username` endpoint + SearchJob/Result modellar
- ✅ Frontend: qidiruv formasi + natijalar jadvali (status badge)
- ✅ Natijalarni DB ga saqlash (tarix) + `/history`, `/jobs/{id}`

## Bosqich 5 — Email / telefon moduli ✅
- ✅ `EmailCollector` (sintaksis + MX + Gravatar)
- ✅ `PhoneCollector` (phonenumbers: davlat/operator/tur/vaqt mintaqasi)
- ✅ `/api/search/email`, `/api/search/phone`
- ✅ Frontend sahifalar (umumiy `SearchModule` komponenti)

## Bosqich 6 — Events (O'zbekiston) ✅
- ✅ RSS aggregator + `/api/events` + `/dashboard/events`
- ✅ Seed manbalar: Gazeta.uz (UZ/RU), Kun.uz
- ✅ Threat intel manbalari: ransomware.live, Telegram (ochiq kanallar + foydalanuvchi akkaunti)
- ✅ Keshlash → keyin DB'ga saqlash (fon yig'uvchi)
- ⬜ Qo'shimcha manbalar: intelforums.cc (qaror kutilmoqda), Reddit (API kaliti kerak)

## Bosqich 7 — Fon yig'uvchi va ogohlantirishlar ✅
- ✅ `events` jadvali, fon yig'uvchi (har 5 daq), dedup
- ✅ Saytdagi ogohlantirishlar 🔔 (`/api/notifications`)

## Bosqich 8–9 — UI qayta dizayn va motion ✅
- ✅ Dizayn tizimi, app shell, grafikli dashboard
- ✅ Motion design (framer-motion); mobil (360px) tekshiruvi va tuzatishlar
- ✅ UI smoke-test (`frontend/scripts/qa/smoke.js`)

## Bosqich 10 — Domen moduli va tarix ✅
- ✅ `DomainCollector`: DNS, SPF/DMARC, WHOIS/RDAP, subdomenlar (CT), ASN; IP: PTR, ASN, RDAP
- ✅ `/api/search/domain` + `/dashboard/domain`
- ✅ Qidiruv tarixi sahifasi (`/dashboard/history`): filtr, qidiruv, natijalarni ko'rish, o'chirish
- ✅ Tarix API: `kind`/`q`/`limit`/`offset`, `DELETE /jobs/{id}`, `DELETE /history`

## Bosqich 11 — Hisobot eksporti va retention ✅
- ✅ `GET /api/search/jobs/{id}/export` (JSON hisobot)
- ✅ JSON yuklash + chop etish sahifasi `/report/[id]` (brauzerda PDF sifatida saqlash)
- ✅ Eksport tugmalari: tarix sahifasi va qidiruv natijasi
- ✅ Events retention (`EVENTS_RETENTION_DAYS`, `EVENTS_RETENTION_KEEP`); sahifalash ("Ko'proq yuklash")

## Bosqich 12 — Events: Markaziy Osiyo, kiber / leak ✅
- ✅ Hudud filtri 5 davlat (UZ, KZ, KG, TJ, TM); mavzu filtri (kiberxavfsizlik / data leak); chet el yangiliklarini kesish
- ✅ Manbalar 5 → 55 (mahalliy yangilik saytlari, UZCERT, xalqaro va rus tilidagi kiber-saytlar)
- ✅ ransomware.live — 5 davlat, bitta so'rov
- ✅ `EVENTS_SINCE` — lenta boshlanish sanasi (eski hodisalar yig'ilmaydi va o'chiriladi)
- ✅ Bloklangan saytlar Google News RSS orqali (`google_news` feed turi); leak kuzatuvchilar (Dark Web Informer, HIBP)
- ✅ Takror yangiliklarni kesish (sarlavha o'xshashligi)
- ⬜ Qo'shimcha manbalar: intelforums.cc (qaror kutilmoqda), Reddit (API kaliti kerak)

## Keyingi — Kengaytirish
- ⬜ Rate limiting, natijalarni keshlash
- ⬜ Bir nechta qidiruvni bitta hisobotga jamlash; Events eksporti
- ⬜ Testlar (pytest), Alembic migratsiyalar
