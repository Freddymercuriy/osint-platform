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
- ✅ Takror voqealar til/sinonimdan qat'i nazar (`events/dedup.py`), bazani tozalash skripti (`scripts/dedup_events.py`); jahon yangiliklari shovqini
- ⬜ Qo'shimcha manbalar: intelforums.cc (qaror kutilmoqda), Reddit (API kaliti kerak)

## Bosqich 13 — Username moduli: faqat Telegram ✅
- ✅ `TelegramAccountCollector`: username / ID → akkaunt, usernamelar, bio, shaxsiy kanal
- ✅ Username tarixi — o'z kuzatuv jurnali (`tg_observations`); avvalgi egasi
- ✅ Umumiy guruhlar va ulardagi xabarlar soni
- ⬜ Kuzatuv ro'yxati: qidirilgan ID'larni fon rejimida qayta tekshirish (qaror kutilmoqda)

## v2 yangilanishi (`feat/v2-upgrade`, spetsifikatsiya: `docs/upgrade-v2-spec.md`)
- ✅ Bosqich 0 — Poydevor: tarmoq + baza nusxasi, Alembic (baseline + stamp, start'da upgrade), rollar va `require_admin`,
  `REGISTRATION_OPEN`, SECRET_KEY tekshiruvi, PyJWT, pytest
- ✅ Bosqich 1 — Ma'lumot modeli: `sources`, `source_runs`, `categories`, `events` yangi ustunlari, eski qatorlarni ko'chirish
- ✅ Bosqich 2 — Yig'uvchi dvigatel: har manba o'z tasodifiy jadvali, backoff, ETag, sog'liq holati, baseline, admin API
- ✅ Bosqich 3 — Manbalar: bazaga seed, Telegram chatlari alohida, yangi threat-intel manbalari
- ✅ Bosqich 4 — Kategoriyalar (15 ta) CRUD va klassifikator, filtrlar
- ✅ Bosqich 5 — Tarjima (en/ru/uz) Google Cloud Translation orqali (kalit kutilmoqda) — 2026-11-16 o'z NLLB servisi bilan almashtirildi
- ✅ Bosqich 6 — Interfeys: Light/Dark/System, uz/ru/en
- ✅ Bosqich 7 — Admin bo'limi va Events sahifasi
- ✅ Bosqich 8 — Interaktiv statistika dashboard'i
- ✅ Bosqich 9 — Xavfsizlik (rate limiting, QA hisobi o'chirildi), testlar, hujjatlar
- ✅ Keyin: Events `range` (soat aniqligida), `TRUSTED_PROXIES` / `X-Forwarded-For`, tarix hisoblagichi
- ✅ Tarjima provayderi: Google Cloud Translation → o'z NLLB servisi (`TRANSLATE_API_URL`, kalitsiz)
- ✅ O'zbek kirill (`uzn_Cyrl`): NLLB `uzn_Latn` + latin.jaybi.uz dvigateli (lotin ↔ kirill)
- ✅ `translit_uz` → jaybi dvigateli; interfeysda "Ўзбекча" (`uz-Cyrl`) tili — xabarlar `uz.json` dan generatsiya
- ✅ Telegram "Arxiv" papkasidagi barcha kanal/guruhlar kuzatiladi (`TG_MONITOR_ARCHIVED`, avtomatik manbalar)
- ✅ NewsNow ulagichi (`newsnow`) + "NewsNow: Cyber Attacks" manbasi (o'chiq, admin yoqadi; scope `global`)
- ✅ Xalqaro kiber-saytlar → Global (migratsiya `0014`, hudud filtrisiz; Markaziy Osiyo haqidagisi baribir regional)
- ✅ Ishlamayotgan manbalar Events'da nomi va sababi bilan (`failing`, HTTP 5xx / Cloudflare 52x izohlari)
- ✅ Kelajak sanali yozuvlar (masalan, The Record RSS `pubDate` ertangi kun) — `published` yig'ish vaqti bilan cheklanadi (`0015`)
- ✅ Telegram: dialoglar chegarasidan (`TG_DIALOG_LIMIT`) tashqaridagi a'zo bo'lingan chatlar ham o'qiladi
- ✅ Admin: Telegram chat tanlash — butun ro'yxat (chegarasiz, 5 daq. kesh), qidiruv, "kuzatilmoqda" belgisi
- ✅ Telegram manbalari → Global + kiber filtri (`0016`); Markaziy Osiyo kalit so'zi bo'lsa — asosiy lentaga
- ✅ Global manbalarda "chet el" qoidasi o'chirildi (NewsNow 85 tadan 26 kiber yangilikni yo'qotardi)
- ✅ Sizish (leak) qoidalari: yolg'iz "breach", yozuvlar soni / hajm, "stolen ... data", dark web / forum (`0017`; 42 hodisa → leak)
- ✅ .onion manbalar Tor orqali: `onion_feed` ulagichi, `tor` konteyneri, kanal `forum`; DarkForums — kiber bo'limlar sarlavhalari (`0024`, egasi qarori 2026-11-20)
- ✅ DarkForums bloklanmaslik qoidalari: lenta jadvali, kichik sahifa, kunlik limit 80, pauza 10–30 s, Premium bo'limlar olib tashlandi (`0025`)
- ✅ Daryo.uz RSS yopildi (403, Cloudflare): UZ → rasmiy Telegram kanali (t.me/s/Daryo), RU → Google News; t.me/s sarlavhasi — birinchi qator (`0026`)
- ⬜ Telegram Global oqimini kuzatish: shovqinli kanallar (BugAlerts ~300/kun) — kerak bo'lsa admin'da o'chirish yoki regional'ga qaytarish
- ⬜ Next 15 ga ko'chish (alohida ish)

## Rahbariyat Telegram kanali (`feat/telegram-channel`, spetsifikatsiya: `docs/telegram-channel-spec.md`)
- ✅ Bosqich 0 — Poydevor: tarmoq, baza nusxasi, sozlamalar (`TG_BOT_TOKEN`, `PUBLISHER_*`, `PUBLIC_APP_URL`),
  Bot API mijozi (`services/publisher/bot.py`) — xato turlari, tokenni yashirish
- ✅ Bosqich 1 — Ustuvorlik: ball / band / sabablar, manba ishonchliligi, kuzatuv ro'yxati (watchlist), energetika va
  transport sohalari, qayta hisoblash, Events'da belgi va filtr (`0018`; jonli tuzatishlar `0019`: "qilin" stem,
  IIV / DXX kuzatuvi o'chiq)
- ✅ Bosqich 2 — Nashr ma'lumot modeli: `channel_destinations`, `channel_posts`, `bot_chats`, `reviewers`, `publisher_state` (`0020`)
- 🟨 Bosqich 3 — Post ko'rinishi: ✅ tezkor xabar / lenta posti (4 til, tozalash, ishonchlilik, tavsiya, hashtag, tugma), ✅ kategoriya `explain_*` / `action_*` (`0021`), ✅ rasmli post (sendPhoto: rubrika | hudud, daraja, 📌 asosiy ma'lumotlar, ⚠️ nima uchun muhim, ✅ tavsiya; 1024 belgiga sig'magani — javob xabari `followup`), ✅ hodisa rasmlari (`event_images`, `0023`: maqola rasmi yoki illyustratsiya, kesh, zaxira; rubrika aniqlash); ⬜ guruhlangan xabar, kunlik brifing, haftalik hisobot + grafik, atama izohi, takror eslatmasi, asl matn bloki
- 🟨 Bosqich 4 — ✅ rejalashtiruvchi (lenta / tezkor), yuboruvchi, bot yangilanishlari (long polling), CLI (`scripts/channel.py`), `require_translation` (`0022`), bitta voqea — bitta post (`stories.py`, tillararo takror); ⬜ tasdiqlash (review chat), yangilanish / tuzatish postlari, brifinglar jadvali
- ✅ Yangiliklar lentasi kanali (o'zbek kirill, hamma hodisa) — egasi talabi, 2026-11-18; token kutilmoqda
- ⬜ Bosqich 5 — Admin: "Kanal" bo'limi (umumiy holat, manzillar, navbat / tarix, kuzatuv ro'yxati, ball + simulyatsiya,
  ko'rinish), Events'da "Kanalga yuborish"
- ⬜ Bosqich 6 — Kalibrlash (14 kun dry-run), test kanalida barcha post turlari, `docs/telegram-channel.md`
- ⬜ Bosqich 7 — Mustahkamlash, hujjatlar, orqaga qaytarish (rollback) yo'riqnomasi

## Keyingi — Kengaytirish
- ✅ Rate limiting (v2 Bosqich 9); ⬜ natijalarni keshlash
- ✅ Events eksporti — CSV / JSON, joriy filtrlar bilan (`GET /api/events/export`, ≤5000, formula himoyasi)
- ⬜ Bir nechta qidiruvni bitta hisobotga jamlash
- ⬜ Manba xato matnlari (`last_error`) interfeys tilida (hozir bazada o'zbek lotinida saqlanadi)
- ✅ Testlar (pytest), Alembic migratsiyalar (v2 Bosqich 0 / 9)
