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

## Bosqich 4 — Username qidiruv moduli
- ⬜ `UsernameCollector` (ko'p saytda profil tekshirish)
- ⬜ `/api/search/username` endpoint + SearchJob/Result modellar
- ⬜ Frontend: qidiruv formasi + natijalar jadvali
- ⬜ Natijalarni DB ga saqlash (tarix)

## Bosqich 5+ — Kengaytirish
- ⬜ Email / telefon moduli
- ⬜ Domen / IP / WHOIS moduli
- ⬜ Hisobot (report) eksporti (PDF/JSON)
- ⬜ Rate limiting, caching
- ⬜ Testlar (pytest, Playwright)
