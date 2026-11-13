# Vazifalar ro'yxati

Belgilar: ✅ bajarildi · 🔄 jarayonda · ⬜ kutilmoqda

## Bosqich 1 — Skelet
- ✅ Git repo, `.gitignore`, `README.md`
- ✅ Hujjatlar (`PROGRESS.md`, `docs/`)
- ✅ Agent ta'riflari (`.claude/agents/`)
- 🔄 GitHub repo + birinchi push

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

## Bosqich 6 — Events (O'zbekiston) 🔄
- ✅ RSS aggregator + `/api/events` + `/dashboard/events`
- ✅ Seed manbalar: Gazeta.uz (UZ/RU), Kun.uz
- ⬜ Foydalanuvchi bergan news saytlarni qo'shish
- ⬜ Reg saytlar (ruxsat tasdiqlangandan keyin)
- ⬜ Keshlash (har so'rovda feedlarni qayta yuklamaslik)

## Bosqich 7+ — Kengaytirish
- ⬜ Domen / IP / WHOIS moduli
- ⬜ Hisobot (report) eksporti (PDF/JSON)
- ⬜ Rate limiting, caching
- ⬜ Testlar (pytest, Playwright)
