# PROGRESS — Bajarilgan ishlar jurnali

> Bu fayl har sessiyada ishni tez davom ettirish uchun. Yangi sessiya boshlanganda **avval shu faylni o'qing**, so'ng `docs/tasks.md` ni ko'ring.

## Hozirgi holat

**Bosqich:** v2 yangilanishi tugadi (Bosqich 0–9) — tarmoq `feat/v2-upgrade` (`main` ga merge qilinmagan; v1 — `main` da).
GitHub'da **default branch — `feat/v2-upgrade`** (2026-11-16, foydalanuvchi talabi bilan; `main` o'zgarmagan). Spetsifikatsiya: [`docs/upgrade-v2-spec.md`](docs/upgrade-v2-spec.md).
**Oxirgi yangilanish:** 2026-11-18

## ▶️ DAVOM ETISH UCHUN

### v2 yangilanishi — davom ettirish nuqtasi
- Ish **`feat/v2-upgrade`** tarmog'ida (`main` ga merge qilinmaydi, force-push yo'q). Har bosqich boshida
  `docs/upgrade-v2-spec.md` ni qayta o'qing; bajarilganlar — `docs/tasks.md` ("v2" bo'limi) va pastdagi "v2 — Bosqich N" yozuvlari.
- v2 dan oldingi baza nusxasi: `~/osint-backups/osint-pre-v2-20261114-145705.sql` (to'liq `pg_dump`).
- Testlar: `docker-compose exec backend pytest` (alohida `osint_test` baza, haqiqiy `.env`/Telegram sessiyasi o'qilmaydi).
- Sxema endi **Alembic** bilan: konteyner ishga tushganda `scripts/start.sh` → `scripts/migrate.py` (`upgrade head`).
  Qo'lda: `docker-compose exec backend python scripts/migrate.py [downgrade -1]`.

### Rahbariyat Telegram kanali — davom ettirish nuqtasi (2026-11-17 dan)
- Ish **`feat/telegram-channel`** tarmog'ida (`feat/v2-upgrade` dan; merge qilinmaydi, force-push yo'q — egasi kanalni
  ko'rgandan keyin o'zi merge qiladi). Spetsifikatsiya: [`docs/telegram-channel-spec.md`](docs/telegram-channel-spec.md)
  — har bosqich boshida qayta o'qing; bosqichlar ro'yxati — `docs/tasks.md` ("Rahbariyat Telegram kanali").
- Baza nusxasi (birinchi migratsiyadan oldin): `~/osint-backups/osint-pre-channel-20261117-164127.sql` (to'liq `pg_dump`).
- Qoidalar: post faqat **alohida bot** bilan (Bot API, `TG_BOT_TOKEN` — faqat `backend/.env`; Telethon akkaunti bilan
  hech qachon); token log / baza / API javobi / xato matniga tushmaydi (`publisher/bot.py::redact`); har yangi kanal
  `dry_run` da boshlanadi; egasi o'zi o'zgartirmaguncha haqiqiy xabar faqat `is_test` kanalga.
- Orqaga qaytish (`feat/v2-upgrade` ga): avval `docker-compose exec backend python scripts/migrate.py downgrade
  0017_leak_rules`, keyin `git checkout feat/v2-upgrade` (start.sh topgan head'gacha ko'taradi, v2 kodi yangi
  reviziyalarni bilmaydi).

### Ishga tushirish (shu kompyuterda)
```bash
docker-compose up -d                      # db + backend + frontend (production build); restart: unless-stopped —
                                          # kompyuter qayta yoqilganda o'zi ko'tariladi. http://localhost:3000
# backend kodi o'zgarsa: docker-compose restart backend  (uvicorn --reload yo'q)
# frontend ishlab chiqish (hot reload): docker-compose stop frontend && (cd frontend && npm run dev)
#   tugagach: docker-compose start frontend   (to'xtatilgan konteyner qayta yoqilganda o'zi ko'tarilmaydi)
# frontend kodi o'zgarsa (production): docker-compose build frontend && docker-compose stop frontend &&
#   docker-compose rm -f frontend && docker-compose up -d frontend
```
3000 va 8000 — `0.0.0.0` da (localhost va LAN: `http://<LAN-IP>:3000`), PostgreSQL 5432 — faqat `127.0.0.1`.

### Boshqa kompyuterda ishga tushirish
Git'da **yo'q** narsalar (qo'lda ko'chirish yoki qayta yaratish kerak):
| Nima | Qayerda | Nima qilish |
|---|---|---|
| `backend/.env` | maxfiy | nusxalash, yoki `cp backend/.env.example backend/.env` va to'ldirish: `SECRET_KEY` (yangi random), `TG_API_ID`, `TG_API_HASH`, `TG_CHATS`, `TG_LEAK_CHATS`, `TG_EXTRA_KEYWORDS`, `TG_MESSAGES_PER_CHAT=100`, `NOTIFY_TELEGRAM=false`, `EVENTS_SINCE=2026-11-10` |
| `backend/data/tg_session.session` | Telegram sessiyasi | nusxalash YOKI qayta login: `docker-compose exec backend python scripts/tg_login.py` |
| Postgres ma'lumotlari | docker volume | ko'chmaydi: foydalanuvchi qayta ro'yxatdan o'tadi, hodisalarni fon yig'uvchi 5 daqiqada o'zi yig'adi |
| `frontend/.env.local` | — | `cp frontend/.env.example frontend/.env.local` |

```bash
git clone https://github.com/Freddymercuriy/osint-platform && cd osint-platform   # yoki: git pull
# backend/.env ni joylashtiring, keyin:
docker-compose build && docker-compose up -d                # db + backend + frontend → http://localhost:3000
# frontend'ni dev rejimida: (cd frontend && npm install && cp .env.example .env.local) va yuqoridagi "ishlab chiqish"
```
Push uchun `gh auth login` kerak. Claude'ga: "PROGRESS.md ni o'qib, davom et" deyish yetarli.

### Yangiliklar lentasi kanali (o'zbek kirill) — Bosqich 3/4 ning bir qismi (2026-11-18)
- Egasining talabi: "yangiliklarni https://t.me/+53mtgEkGJhdjMzky kanaliga yuklab borsin, har biri o'zbekcha" →
  tanlov: **hamma hodisa** (global ham, kuniga ~220), **o'zbek kirill**. Spetsifikatsiyadan chetlanish: rahbariyat
  kanali faqat kritik + brifinglar edi; bu kanal — lenta (`scripts/channel.py add --feed`).
- Kod (`services/publisher/`): `render.py` — post (sarlavha qatori: band nuqtasi + yorliq · bayroq + davlat ·
  kategoriya; tarjima qilingan sarlavha, 1–2 gap, Toshkent vaqti, ishonchlilik + manbalar, yuqori/kritikda tavsiya,
  ASCII hashtag, "Manbani ochish" tugmasi; URL / email / telefon / @mention / emoji / reklama qatorlari olib
  tashlanadi, .onion va fayl havolalariga tugma yo'q; kirill — tozalashdan KEYIN, faqat matn maydonlariga; ≤ 900
  belgi). `planner.py` — har 30 s: nomzodlar (enabled_at dan keyin, 24 soat, baseline emas, band / davlat / global /
  kategoriya filtri), `dedup_key=alert:<id>`, tarjimani kutish (`require_translation` — asl matn hech qachon,
  6 soatdan keyin `skipped/translation_missing`), rejim (dry_run → `skipped/dry_run` matni bilan; review / yagona
  manbasi underground → `awaiting_approval`), sokin soatlar, kunlik chegara. `sender.py` — har 5 s, chat bo'yicha
  ≥ 1,1 s va ≤ 18/daqiqa; 429 / parse xatosi (oddiy matn) / 403 (kanal down) / 401 (bot invalid) / tarmoq;
  `sending` → restartda `unknown`; 6 soatda `expired`. `updates.py` — long poll: `my_chat_member` → `bot_chats` va
  kanal sog'lig'i, `/start` → Telegram ID. `runner.py` — o'z advisory lock'i (`72_620_261_115`), token yo'q — faqat
  dry-run (`bot_status=token_missing`); `main.py` lifespan'da.
- Migratsiya `0022_require_translation`: `channel_destinations.require_translation`, `max_instant_per_day` chegarasi
  100 → 1000 (downgrade 100 ga qisqartiradi). `core/i18n.py`: `pub_*` katalogi (avvalgi sessiyadan WIP) + 
  `pub_conf_tracker`, `pub_conf_community`, `pub_start_reply`, `pub_review_unavailable`; `pub_t_outage` uz `{place}`.
  `0021_category_texts` (WIP: `explain_*`, `action_*`) ham shu commit'da.
- 🔔: `channel_down`, `bot_token_invalid`, `post_unknown`, `webhook_conflict` o'z matni bilan (uz/ru/en + uz-Cyrl).
- Tekshirildi: 21 yangi test (soxta Telegram, `httpx.MockTransport`; token xato/log/bazaga tushmaydi); haqiqiy
  baza ustida vaqtinchalik dry-run kanali — 60 post, kirill, ≤ 518 belgi. **Tekshirilmadi:** haqiqiy Telegram
  (token yo'q), Telegram orqali tasdiqlash (review chat), brifing / haftalik hisobot, admin "Kanal" sahifasi.
- **Ulandi (2026-11-18):** bot @messageosi_nt_bot, kanal «osint» (`-1004306867669`, yopiq) → manzil `[5] osint`, `--feed`, sinov xabari yuborildi (message_id 4), `mode=auto`. `my_chat_member` kelmadi (bot token qo'yilishidan oldin qo'shilgan) — zaxira yo'l qo'shildi: kanaldagi istalgan post (`channel_post`) yoki botga forward qilingan kanal posti → `getChatMember` → `bot_chats`.
- Ishga tushirish (egasi): @BotFather → bot; botni kanalga admin ("Post messages"); `backend/.env` ga
  `TG_BOT_TOKEN=...`; keyin konteynerni qayta yaratish (`docker-compose stop backend && docker-compose rm -f backend
  && docker-compose up -d backend`), so'ng `python scripts/channel.py chats` → `add --chat <id> --name ... --feed`
  → `preview` → `test` → `set <id> mode=auto`.

### Tarjima navbati: "til almashtirdim, kontent o'zgarmadi" (2026-11-18)
- Sabab: NLLB servisi (umumiy GPU, `batch_size=16`) band paytda 15–40 s javob beradi; worker 64 talik paketni 30 s
  kutardi → butun paket timeout, 3 urinishdan keyin `failed` (ru ~37%, uz ~41% qatorlar tarjimasiz; eng yangi
  hodisalar lenta tepasida inglizcha / asl tilda qolardi).
- `services/i18n/worker.py`: paket ≤ 16 matn / 4000 belgi; timeout'da paket ikkiga bo'linib darhol qayta yuboriladi,
  ketma-ket 2-timeout'da navbat 5 daqiqa tanaffus (`stopped="timeout"`); bitta chaqiruv ≤ 150 s (`time_budget`,
  qolgani keyingi tick'da, urinish hisoblanmaydi); backoff ≤ 60 daqiqa; vaqtinchalik xato bilan `failed` qator
  6 soatdan keyin o'zi `pending` ga qaytadi (`requeue_due_failed`; 422 / noma'lum til — `next_attempt_at` siz, qaytmaydi);
  navbat so'rovi `populate_existing` bilan.
- `translator.py`: `TranslationTimeout` (alohida xato turi); `/model` javob bermasa standart chegara 10 daqiqa
  keshlanadi (avval har paket oldidan sekin `/model` kutilardi). `TRANSLATE_TIMEOUT_SECONDS` standarti 30 → 90.
- Frontend `lib/api.ts::currentLocale`: `uz-Cyrl` cookie "uz" deb o'qilardi → backend xabarlari lotinda kelardi.
- Testlar: +7 (paket hajmi, bo'lish, tanaffus, avto-qayta navbat, `/model` keshi).
- Ma'lum: saqlangan tekshiruv natijalari (username/email/telefon/domen) tekshiruv paytidagi tilda qoladi — dizayn
  (`core/i18n.py`), yangi tekshiruv tanlangan tilda.

### Rahbariyat kanali — Bosqich 2: nashr ma'lumot modeli (2026-11-17)
- **Migratsiya `0020_publishing`** (downgrade bor), modellar `models/publisher.py`:
  - `channel_destinations` — nom, `chat_id` (dry-run uchun bo'sh bo'lishi mumkin), chat nomi / turi / `chat_username`
    (bor bo'lsa — ochiq kanal), `topic_id`; `lang` (uz | uz-Cyrl | ru | en), `mode` (dry_run | review | auto,
    standart dry_run), `is_test`; qamrov: `countries` (standart 5 ta), `include_global`, `categories` (bo'sh = hammasi),
    `instant_min_band` (critical), `brief_min_band` (medium); jadval: kunlik (08:30, Du–Ju), haftalik (Du 08:45);
    sokin soatlar 22:00–07:00 va `quiet_policy` (`uz_sound` — faqat O'zbekiston kritik ovozli, boshqa kritik ovozsiz,
    high — brifingga; `all_silent`; `hold`); `max_instant_per_day` (6); `protect_content` (standart **false** —
    rahbarlar postni xodimlariga forward qilib topshiriq beradi), `show_original`, `explain_terms`; holat: `enabled`,
    `enabled_at` (yaratilganda — hozir: yoqish eski hodisalar bilan to'ldirmaydi), pauza + sabab, sog'liq (`status`
    unknown/ok/down, `down_since`, oxirgi muvaffaqiyat / xato, ketma-ket xatolar, `rights` + tekshirilgan vaqt).
  - `channel_posts` — tur (alert, group, daily, weekly, update, correction, test), `event_ids` (GIN indeks),
    `(destination_id, dedup_key)` noyob, 11 holat (check), muzlatilgan `text` + `edited_text` (`final_text`), tugmalar,
    `photo` (haftalik grafik PNG), `silent`, `reply_to_post_id` (SET NULL), yetkazish (`chat_id`, `message_id`,
    `scheduled_at`, urinishlar, keyingi urinish, `last_error` — token yashirilgan, `skip_reason`), tasdiqlovchi (web
    foydalanuvchi yoki Telegram id / ism, vaqt), tekshiruv chatidagi qoralama id, yuborish paytidagi band va manbalar
    soni, `meta`. Tozalanmaydi (≥ 1 yil talabi; hodisalar 90 kunda o'chsa ham post qoladi — `event_ids` FK emas).
  - `bot_chats` (chat_id PK, tur, nom, username, botning holati va huquqlari, kim qo'shgani), `reviewers`
    (`tg_user_id` noyob, platforma foydalanuvchisiga bog'lanishi mumkin), `publisher_state` (id = 1: offset, umumiy
    pauza, tekshiruv chati, bot holati — unknown/missing/ok/invalid/conflict/error).
- `services/publisher/outbox.py` — `insert_post` (`INSERT ... ON CONFLICT DO NOTHING`: restart va ikki marta ishlagan
  tsikl takror post yaratmaydi), `get_state`, `find_post`. Test seed'iga `publisher_settings`, `publisher_state`.
- AdminAlert uchun yangi ustun kerak emas: kanal ogohlantirishlari `data.destination_id` bilan (Bosqich 4).
- **Tekshirildi:** `test_publisher_model.py` (standart qiymatlar, 5 cheklov, dedup idempotentligi, holat / tur
  cheklovlari, `final_text`, javob havolasi SET NULL, kaskad, holat qatori, bot_chats, reviewers noyobligi);
  `test_migrations.py` (up/down/up); jonli baza: 0020 qo'llandi, standart qiymatlar (tranzaksiyada qo'shib, rollback);
  to'liq pytest.
  **Tekshirilmadi:** —

### Rahbariyat kanali — Bosqich 1: ustuvorlik (2026-11-17)
- **Migratsiya `0018_priority`**: `events.priority` (smallint, indeks), `priority_band` (low/medium/high/critical, check),
  `priority_reasons` (JSONB `[{code, points, arg?}]`); `sources.reliability` (official / tracker / media / community /
  underground) — turi va nomidan seed: official 7 (CISA KEV, NVD, UZCERT, KZ-CERT, CERT.TJ, KG-CERT, sts.kz), tracker 9,
  underground 9 (TG_LEAK_CHATS / leak qat'iy kategoriyali chatlar), community 34, media 62; `watchlist` jadvali —
  `TG_EXTRA_KEYWORDS` dan 20 ta tashkilot / brend (joy nomlari olinmadi; umumiy so'zlar "soliq", "mehnat", "ipoteka"
  yolg'iz alias emas — aniq nom bilan); `publisher_settings` (id = 1) — og'irliklar va band chegaralari (spetsifikatsiya
  jadvali). Downgrade bor.
- **Sof funksiya** `services/publisher/priority.py::compute` — ball 0–100, band, sabablar (planner, Events va
  simulyatsiya bir xil natija oladi). `record_count` — `pwn_count` yoki matndan ("8.3M records", "40M-record",
  "44,080-member", "1,2 млн записей"). Manba identifikatori — "X (Google News)" = "X" (nusxa qayta sanalmaydi).
  Global + kuzatuvsiz → ball 39 gacha, band low (`global_cap` sababi manfiy ball bilan — ball va band mos).
  Hodisa `severity` si ishlatiladi (kategoriya jiddiyligi + ulagich ko'targan daraja, masalan KEV) — spetsifikatsiyadagi
  "category severity" bilan bir xil manba.
- **Kuzatuv ro'yxati** (`publisher/watchlist.py`): butun so'z, apostrof variantlari (`filters._kw_regex`), o'zbekcha
  lotin ↔ kirill avtomatik (jaybi); sarlavha, matn, tarjimalar, `matched_keywords`, `extra.victim/domain`.
- **Sohalar**: `dedup._SECTORS` + `geo.SECTOR_NAMES` ga ENERGY / TRANSPORT ("airways", "pipeline", "power" — ataylab
  yo'q: "PowerShell", CI "pipeline" shovqini).
- **Qayta hisoblash** (`publisher/scoring.py`): `store_items` (yangi + boshqa manba qo'shilgan — `touched_ids`),
  tarjima tugaganda (`ProcessStats.done_event_ids`), admin kategoriyani o'zgartirsa, qayta tasniflash, kategoriya
  jiddiyligi / o'chirish, manba ishonchliligi (shu manba, 14 kun), kuzatuv ro'yxati va og'irliklar (14 kun),
  housekeeping — `priority is null` (migratsiyadan keyin 1193 ta hodisa shu yo'l bilan hisoblandi).
- **API**: `GET /api/events?band=...` (va eksport), `EventItemOut.priority/priority_band/priority_reasons`; CSV/JSON
  eksportga `priority`, `priority_band` ustunlari; admin: `/api/admin/publisher/watchlist` (CRUD, `/{id}/test`,
  `POST /watchlist/test` — saqlanmagan yozuvni sinash, 30 kun), `/api/admin/publisher/settings` (GET/PUT, band
  tartibi tekshiriladi); manba formasi / import / eksport / arxiv — `reliability`.
- **Frontend**: Events kartasida `PriorityBadge` ("Yuqori · 65"; bosilganda / ustiga kelganda sabablar ro'yxati —
  telefonda ham), filtr panelida "Ustuvorlik" (band) guruhi va chip; admin manba formasida "Ishonchlilik" tanlovi.
  Tarjimalar uz/ru/en + uz-Cyrl (963 kalit × 4).
- **Jonli tekshiruvda topilgan va tuzatilgan (`0019`)**:
  1. ransomware qoidasidagi `qilin` stem o'zbekcha "jalb **qilin**adi" ga mos kelardi — Kun.uz "Kiberfiribgarlikka
     qarshi tezkor markaz ochiladi" ransomware / critical bo'lib 🔔 bergan. Endi butun so'z; faqat shu stem bilan
     tasniflanganlar qayta tasniflandi (1 ta → other; 3 ta haqiqiy Qilin hodisasi ransomware'da qoldi).
  2. kuzatuvdagi IIV va DXX — 5 ta moslikning 5 tasi ular hodisani **xabar qilgan** yangiliklar edi (pora, markaz
     ochilishi) → o'chirib qo'yildi (izoh bilan; admin yoqa oladi).
- **Jonli taqsimot** (1200 hodisa): regional — critical 3, high 10, medium 21, low 68; global — medium 1, qolgani low.
  Kalibrlash (kunlik tezkor xabarlar soni) — Bosqich 6 da.
- **Tekshirildi:** `test_publisher_priority.py` (30 test: og'irliklar, bandlar, global chegara, yozuvlar soni,
  kuzatuv — lotin/kirill/apostrof/butun so'z/domen, store_items + birlashish, kategoriya o'zgarishi, housekeeping,
  kuzatuv CRUD + qayta hisoblash, sozlamalar PUT + validatsiya, ishonchlilik seed / API, band filtri);
  `test_categories.py` (+3 Qilin misoli); to'liq pytest (5 m 29 s, migratsiyalar up/down/up); typecheck, i18n,
  frontend qayta qurildi, smoke (14 sahifa × 2) toza; CDP: Events `?band=critical,high` — 10 karta, sabablar oynasi
  (desktop va 360 px, gorizontal skroll yo'q).
  **Tekshirilmadi:** kuzatuv / sozlamalar admin UI (Bosqich 5 da).

### Rahbariyat kanali — Bosqich 0: poydevor (2026-11-17)
- Tarmoq `feat/telegram-channel`, baza nusxasi (yuqorida), spetsifikatsiya `docs/telegram-channel-spec.md` (o'zgarishsiz).
- Sozlamalar (`core/config.py`, `.env.example`): `TG_BOT_TOKEN` (bo'sh — faqat dry-run), `PUBLISHER_ENABLED=true`,
  `PUBLISHER_TRANSLATION_WAIT_MINUTES=10`, `PUBLIC_APP_URL` (bo'sh — "Platformada ochish" tugmasi yo'q).
  `NOTIFY_TELEGRAM` hujjatlarda "eski (legacy)" deb belgilandi (o'zgarmadi).
- `services/publisher/bot.py` — httpx ustida Bot API mijozi (getMe, getWebhookInfo, getUpdates, getChat, getChatMember,
  sendMessage, sendPhoto (multipart), editMessageText, editMessageReplyMarkup, deleteMessage, answerCallbackQuery).
  `raise_for_status` yo'q — javob JSON'idan `ok/error_code/description/parameters`. Xato turlari: `BotRateLimited`
  (`retry_after`), `BotUnauthorized` (401/404), `BotForbidden` (403), `BotBadRequest` (`is_parse_error`,
  `chat_not_found`, `too_long`, `not_modified`, `message_gone`), `BotConflict` (409), `BotNetworkError` (tarmoq,
  timeout, 5xx, JSON emas), `BotTokenMissing`. Token: `redact()` har xato matnida, httpx istisnosi zanjirsiz
  (`from None`), `httpx` / `httpcore` / `osint.publisher` loggerlariga yashiruvchi filtr (httpx INFO satri URL'ni token
  bilan yozadi).
- Bot API hujjati 2026-11-17 da o'qildi: versiya **10.4** (2026-11-09; spetsifikatsiyada 10.3). Farqlar: `my_chat_member`
  standart keladi; 409 Conflict hujjatda yozilmagan (himoyaviy ishlov); `sendRichMessage` bor — ishlatilmaydi.
- **Tekshirildi:** `test_publisher_bot.py` (13 test: so'rov shakli, multipart, 8 xato turi + 2 tarmoq xatosi — token
  xato matni, repr, traceback va loglarda yo'q); to'liq pytest; backend qayta ishga tushdi.
  **Tekshirilmadi:** haqiqiy Telegram (token yo'q).

### 2026-11-14, 2-sessiya davomi (Bosqich 12: Markaziy Osiyo + kiber/leak filtri, "bugundan boshlab")
Foydalanuvchi talabi: *"yangiliklar bugundan boshlab ko'rsatilsin, eskilari kerak emas; mazmuni kiberxavfsizlik yoki data leak
bo'yicha, Markaziy Osiyo davlatlari uchun bo'lsin"*.
- **Boshlanish sanasi** — `EVENTS_SINCE` (`backend/.env` da `2026-11-14`; bare sana = Toshkent vaqti bilan kun boshi):
  undan oldingi hodisalar **barcha kategoriyalarda** yig'ilmaydi va har tsiklda bazadan o'chiriladi (`collector.is_expired`,
  `_purge_expired`). `GET /api/events/status` → `since`; Events panelida "14 noy 2026 dan boshlab". Bo'sh qiymat = chegara yo'q.
  ⚠️ Bu 2023-yildan beri yig'ilgan 6 ta ransomware yozuvini ham o'chirdi (foydalanuvchiga aytilgan). Tozalashdan oldingi to'liq nusxa
  (141 qator): `~/osint-events-backup-2026-11-14.sql` (repodan tashqarida; `backend/data/` root'ga tegishli — yozib bo'lmadi).
- **Hudud filtri** — endi 5 davlat (UZ, KZ, KG, TJ, TM): `feeds.REGION_KEYWORDS` (davlat/shahar o'zaklari lotin+kirill, `.uz .kz .kg .tj .tm`
  domenlari, "central asia"...). `UZ_KEYWORDS` — alias. `TG_UZ_FILTER=true` endi "Markaziy Osiyo filtri" (UI'da "MO filtr").
- **Mavzu filtri** — `TOPIC_STEMS` + `TOPIC_PATTERNS` (kontekstli regexlar: "утечка" yolg'iz emas, "мошенничество" faqat online
  kontekst bilan) − `TOPIC_NOISE` (киберспорт, "взлом квартиры", "утечка газа"). uz/ru/en, qisman kk.
- **Feed bayroqlari:** `cyber_filter` (mahalliy saytlar — faqat mavzu) va `region_filter` (xalqaro kiber-saytlar — faqat hudud;
  eski `uz_filter` endi shuning property'si). Mahalliy saytlar uchun qo'shimcha qoida: matnda chet el belgisi
  (`FOREIGN_MARKERS`: AQSH, FQB, KXDR, "global"...) bo'lib, mintaqa so'zi yo'q bo'lsa — yozuv tashlanadi (qayta bosilgan jahon
  yangiligi); manbaning o'z domeni ("...Tengrinews.kz") mintaqa belgisi hisoblanmaydi (`_strip_own`).
- **Manbalar: 5 → 55** (keyin +8 = 63, pastga qarang) (`feeds.py`): UZ (Gazeta, Kun, Spot, Daryo, UzDaily, Nuz, **UZCERT** — filtrsiz), KZ (Tengrinews, Kursiv,
  Profit.kz, DigitalBusiness, Sputnik), KG (24.kg, Kaktus, AKIpress, Kloop, Kabar, Sputnik), TJ (Asia-Plus, Sputnik),
  TM (Turkmen.news, Хроника Туркменистана), CentralAsia.media; xalqaro kiber (The Hacker News, SecurityWeek, The Record,
  DataBreaches, Securelist, Security Affairs, HackRead, Krebs, Dark Reading, ... + Xakep, SecurityLab, Anti-Malware, Habr, Kaspersky).
  403/Cloudflare berganlar qo'shilmadi (BleepingComputer, CyberNews, CISA...). 53 ta RSS parallel (16 tadan) ≈ 5 s.
- **ransomware.live:** endi bitta `/v2/recentvictims` so'rovi (oxirgi ~100 qurbon), `country` ∈ {UZ,KZ,KG,TJ,TM} yoki milliy domen
  bo'yicha filtr (rate limit 1/daq — 5 ta alohida so'rov o'rniga). Sarlavha: `[guruh] Qurbon (KZ)`.
- UI matnlari "O'zbekiston" → "Markaziy Osiyo" (sidebar, Events, landing, login/register, kategoriya tavsiflari).
- Agent: `osint-collector` (manbalar + filtr); sana chegarasi, chet el qoidasi, UI va tekshiruv — asosiy sessiyada.
- **Hozirgi holat:** baza tozalangan, lenta **bo'sh** (bugun mos hodisa chiqmagan — kutilgan holat). Jonli sinov (2117 ta RSS yozuv):
  mavzu filtridan 10 ta o'tdi, 6 tasi chet el qoidasi bilan tashlandi, qolgan 4 tasi 14-noyabrdan oldingi; UZCERT'ning 10 ta
  yozuvi ham 10–12-noyabrga tegishli.
- Tekshirildi: ✅ birlik testlar (hudud/mavzu/chet el/sana, konteyner ichida); ✅ jonli RSS (53 feed, 0 xato); ✅ purge (30 eski yozuv);
  ✅ `tsc`, build, smoke 22/22 (bo'sh lenta bilan).
- ⚠️ Tekshirilmadi: haqiqiy mos hodisaning oxirigacha yo'li (RSS → baza → UI → 🔔) yangi filtr bilan — bugun mos yozuv bo'lmadi;
  ransomware.live'da Markaziy Osiyo qurbonining kelishi (sun'iy javobda sinalgan); Telegram oqimi yangi kalit so'zlar bilan
  (faqat regex darajasida); qozoq/tojik/turkman tilidagi mavzu so'zlari real matnda.
- Sozlash: filtr juda qattiq/yumshoq bo'lsa — `feeds.py` dagi `TOPIC_*`, `FOREIGN_MARKERS`; eski hodisalar kerak bo'lsa —
  `EVENTS_SINCE` ni o'zgartirish/bo'shatish (manbalar hali qaytarayotganlarini yig'uvchi qayta yozadi).

### v2 dan keyin — "manbalar ishlayapti, ma'lumot kelmayapti" tahlili; xalqaro kiber-saytlar Global (2026-11-16)
- Foydalanuvchi: *"107 ishlaydigan manbadan ma'lumot keladiganga o'xshamayapti"*. Tahlil (quruq yurgizish, 48 soat):
  mahalliy yangilik saytlari (31, kiber filtri) — 830 element → 24 o'tdi (510 tasi mintaqa haqida, 27 tasi kiber);
  xalqaro kiber-saytlar (25, hudud filtri) — 168 → 1; `site:` Google News (3) — 0–1; Telegram (43) — kalit so'z
  filtri connector ichida (`source_runs.items` = filtrdan keyingi son), 39 tasidan hech qachon hodisa yo'q; sessiya
  2026-11-16 10:25 UTC gacha `auth_missing` edi. Xato yo'q — filtrlar (Markaziy Osiyo + kiber) kesadi: ~25–30
  regional hodisa / sutka. Sanalar to'g'ri (Dark Reading, ESET va b. — oxirgi maqolalar 11–13 noyabr).
- Foydalanuvchi tanlovi — 2-variant: migratsiya `0014_international_cyber_global` — RSS (`region_filter` yoqiq,
  `cyber_filter` o'chiq; 25 ta) va `site:` Google News (BleepingComputer, CyberNews, The Cyber Express — so'rovdan
  Markaziy Osiyo sharti olindi) → `scope=global`, hudud filtrisiz; `baseline_done=false` + ETag tozalandi —
  birinchi yig'ish ogohlantirishsiz (🔔 oqimi yo'q). `pipeline.store_items`: global manbaning (`it.scope` berilmagan)
  Markaziy Osiyo belgisi bor elementi → `regional` (+ `matched_keywords`) — asosiy lenta avvalgidek to'liq.
  Kutilgan oqim: ~80 global kiber yangilik / sutka ("Global" filtrida). Testlar: `test_global_cyber_sources.py`.
- HTTP 522 (HackRead — sayt serveri, Cloudflare ulana olmayapti): `http.SERVER_ERRORS` / `http_error_text` —
  5xx va Cloudflare 52x uchun izoh ("HTTP 522 — Cloudflare: sayt serveri javob bermadi ..."). `/api/events/status`:
  `failing` (yoqilgan down/blocked manbalar, ≤5: nom, sabab, HTTP, keyingi urinish, Retry-After) + `failing_total`;
  `last_error` endi manba nomi bilan. Events: qizil "Yig'uvchi xatosi" o'rniga sariq `FailingSources` ("N ta manba
  ishlamayapti — yig'uvchining o'zi ishlayapti ...", ro'yxat). `events.collectorError` kaliti olib tashlandi.
- 2026-11-17 tekshiruv: migratsiya jonli bazada qo'llangan (`alembic_version = 0014`). U **26** ta RSS'ni o'zgartirdi
  (25 ta yoqilgan + o'chiq "Have I Been Pwned" RSS — 0007 da API bilan almashtirilgan; zararsiz), test shunga moslandi.
  `downgrade` endi faqat `Global (0014)` belgili qatorlarni qaytaradi (keyin admin qo'shgan global RSS'ga tegmaydi).
  Jonli: 28 ta manba baseline'ni 03:38–04:01 UTC da tugatdi — 541 global (hammasi baseline, 🔔 yo'q) + 4 regional;
  `/api/events/status` → `failing_total=3` (Google News (RU) — 429; 2 ta Telegram chat — "Chat topilmadi yoki akkaunt
  a'zo emas": SecurelyContactingAZRAEL, crackedstatusupdate). The Record RSS'da `pubDate` ertangi (18-noyabr 01:20 GMT) —
  manbaning o'zi; lenta tepasida turib qolardi — pastdagi tuzatish bilan hal qilindi. To'liq pytest (3a67b8d) — hammasi o'tdi.
- **Kelajak sanasi cheklanadi** (foydalanuvchi: *"yes, cap future dates"*): `pipeline.store_items` — `published > now`
  bo'lsa `published = now` (yig'ish vaqti), asl sana `extra.published_original`. Migratsiya `0015_cap_future_published`
  mavjudlarini tuzatdi (`published > first_seen` → `first_seen`; jonli bazada 1 ta — The Record "Uber ... 150,000",
  endi 03:41 UTC); downgrade asl sanani qaytaradi. Test: `test_future_published.py`.
- **Telegram: chegaradan tashqaridagi chatlar** — foydalanuvchi SecurelyContactingAZRAEL va crackedstatusupdate ga qo'shildi,
  lekin xato qolaverdi: akkauntda 698 dialog, bu ikkisi 117- va 138-o'rinda (Telegram tartibi — oxirgi xabar sanasi;
  kam yoziladigan kanal pastda), yig'uvchi esa birinchi `TG_DIALOG_LIMIT=100` tasini ko'radi. Tuzatish:
  `telegram_user._resolve_joined_chat` — dialoglarda topilmasa username / ID bo'yicha aniqlanadi (avval sessiya keshi,
  so'ng `get_entity`), faqat a'zo bo'lingan kanal/guruh (`left`/bot/shaxsiy — rad), natija `_dialog_cache` ga.
  Jonli: ikkala manba `ok` (AZRAEL — 1 ta mos xabar). Test: `test_telegram_resolve.py`.
- **Admin chat tanlash — butun ro'yxat:** `/api/telegram/chats` endi `list_chats(full=True)` (chegarasiz, 5 daq. kesh;
  `?refresh=true` — `refresh_rate` limiti bilan), har chatda `monitored` va `archived`. `SourceForm` → `TelegramPicker`:
  qidiruv (nomi / @username / ID), "Yangilash", "Ko'rsatilgan: N / M", "✓ kuzatilmoqda" belgisi (4 til).
  Jonli: 227 chat (avval 105), birinchi so'rov 3.2 s, keshdan 0.1 s; 43 tasi kuzatilmoqda.
- **Telegram → Global** (foydalanuvchi tanlovi: *"All 43 channels"* + 🔔 *"Keep all"*). Tahlil (sessiya nusxasi bilan,
  faqat o'qish): 43 manbaning so'nggi 2728 xabaridan eski filtr (Markaziy Osiyo + `TG_EXTRA_KEYWORDS`) 31 tasini (~1%)
  o'tkazardi, kiber mavzusi — 460. O'zgarishlar:
  - Telegram ulagichi `scope=global` manbada kalit so'zni talab qilmaydi; kalit so'z topilgan xabar `regional`
    (`RawItem.scope`), `apply_filters` global manbada mintaqaga oid elementni kiber mavzusisiz ham o'tkazadi —
    asosiy lenta kamaymaydi. Regional Telegram manbasi — avvalgidek.
  - "Chet el" qoidasi faqat regional manbalarga (NewsNow 85 kiber yangilikdan 26 tasini — "FBI warns ..." —
    tashlardi). `FilterSource.scope` (yo'q bo'lsa regional).
  - Migratsiya `0016_telegram_global`: barcha `telegram_user` → global + `cyber_filter`, kursor (`state.last_id`)
    olib tashlandi, `baseline_done=false`. Arxivdan avtomatik yaratiladigan manbalar ham global + kiber filtri.
  - `RawItem.ignore_source_category`: "leak" kategoriyali chatning mintaqaga oid bo'lmagan global xabari
    klassifikator bilan (`extra.category_free`, `reclassify` ham hurmat qiladi). Sabab: baseline'da "Hi",
    "yo mb super hacker bro" kabi suhbat "leak" bo'lib qolgan — jonli oqimda Breachforums Databases v2 chati
    (~2300 xabar/kun) yolg'iz ~115 🔔/kun berardi. Mavjud 13 qator belgilandi, `reclassify` 9 tasini o'zgartirdi
    (leak → other 7, credentials 1, ddos-outage 1).
  - Jonli: 43 manba baseline'ni tugatdi, xato 0; 238 global (hammasi baseline, 🔔 yo'q, 21 manbadan; BugAlerts —
    100 tasi), regional Telegram 7 → 8. Testlar: `test_telegram_sources.py`, `test_connector_newsnow.py`.
  - ⚠️ Kuzatish kerak: BugAlerts (~300/kun, asosan `vulnerability` — 🔔 yo'q) Global lentani bosadi; kerak bo'lsa
    admin'da o'chirish yoki `scope=regional` ga qaytarish.
- **Events eksporti (CSV / JSON)** — backlog'dagi ⬜. `GET /api/events/export` (`services/events/export.py`):
  Events ro'yxati bilan bir xil filtrlar (`event_filters`, scope, `range`) va ko'rsatish tili (`localize`), eng yangi
  5000 ta; CSV — BOM + formula injection himoyasi (tashqi matn: Telegram, RSS), ustunlar: id, sanalar, scope,
  kategoriya, daraja, sarlavha/matn, havola, manba, kanal, davlatlar, soha, guruh, kalit so'zlar, also_reported_by,
  til, asl sarlavha; JSON — `filters`, `total`, `truncated`. CORS `expose_headers` (fayl nomi, son). Frontend:
  Events'da "Eksport: CSV · JSON" tugmalari (son yonida), natija matni ("N ta hodisa yuklandi" / chegara), 4 til.
  `statsApi.downloadCsv` ga ham formula himoyasi. Jonli: regional 92, global 959, 7 kun 1023 — fayllar brauzerda
  yuklandi (desktop + 360px). Test: `test_events_export.py`.
- **Telegram belgisi haqiqiy sonni ko'rsatadi:** Events'da "22 ta chat · hudud filtri" (`.env` `TG_CHATS` va
  `TG_UZ_FILTER`) eskirgan edi — kuzatilayotgani 43 ta manba, hammasi Global (0016). `/api/telegram/status` →
  `sources`, `global_sources` (yoqilgan `telegram_user` manbalari); belgi: "43 ta chat · Global: 43"; admin →
  Tizim → Telegram kartasida ham ikki yangi qator. Test: `test_telegram_resolve.py`.
  ⚠️ Ma'lum: manba xato matni (`last_error`) bazada o'zbek lotinida — kirill/rus interfeysda lotin ko'rinadi.
- **Sizish (leak) qoidalari kengaytirildi** (`0017_leak_rules`; foydalanuvchi: *"yes fix the leak rules"*).
  Sabab: `@dailydarkweb` ("TG: Dark Web Intelligence") va yangiliklardagi sizishlar "other" da qolib, 🔔 bermagan —
  "Infoblox confirms a third-party vendor breach", "GUINEA ... 2.8GB DATABASE, 8.3M RECORDS" (ball 0). Bo'shliqlar:
  yolg'iz "breach" (faqat "breached" / "data breach" bor edi), yozuvlar soni / hajm ("8.3M records", "40M-record",
  "2.8GB database"), "stolen ... data" (eski pattern "stole " dan keyin bo'shliq kutardi), "customer / member /
  consumer database", "citizen data", "data dump / theft / exposure", "data ... on dark web / cybercrime forum".
  Ransomware: "ransomware group/gang/operators" pattern — "ransomware group ... stolen data" maqolasi leak'ka o'tmaydi.
  Qoidalar ustidan yozilmaydi (admin tahrirlari saqlanadi) — faqat yo'q stem / pattern qo'shiladi; downgrade aynan
  shularni olib tashlaydi. Hodisalar: faqat shu o'zgarish ta'sir qilganlari (eski qoidalar saqlangan kategoriyani
  bergan) ko'chiriladi, oldingisi `extra.category_before_0017` da. Jonli: **42 ta → leak** (other 30, credentials 4,
  vulnerability 3, fraud 2, malware 2, darkweb-sale 1; ransomware'dan 0); 34 tasi baseline (🔔 yo'q), 8 tasi 🔔
  ro'yxatida, yangi o'qilmagan 0. Muhim topilma: #1262 "Qozog'iston Oliy sudi ma'lumotlari darknetda $50 000" —
  regional, avval "other". Chegaraviy (~6): "exploit X to breach Y" — vulnerability/malware edi; mavjud "breached"
  stem bilan izchil. Test: `test_categories.py` (11 yangi misol + qo'shish/olib tashlash).

### v2 dan keyin — bloklash / rate limit kutishi ko'rinadi; NewsNow doimiy (2026-11-16)
- Foydalanuvchi talabi: *"doimiy kuzatishi kk ... agar sayt bloklasa 5 min rate limitmi yoki qancha vaqt kk bo'lsa
  shunda ko'rinadigan qilib ber"*.
- Avval: 429 / 403 / challenge → `blocked`, kutish = max(backoff, Retry-After) hisoblanardi, lekin saqlanmasdi —
  rate limit va blok farqi va sayt so'ragan vaqt ko'rinmasdi.
- Migratsiya `0013_source_wait_info`: `sources.last_outcome`, `sources.retry_after_seconds`;
  `source_runs.retry_after_seconds`, `source_runs.wait_seconds` (mavjud manbalarga `last_outcome` tarixdan).
  `scheduler.run_source`: har urinishda yoziladi, muvaffaqiyatda `retry_after_seconds` tozalanadi; log'da ham.
  `RunSummary` / `TestResult` / API (`SourceOut`, `RunOut`, `RunNowOut`, `TestOut`) — yangi maydonlar.
- Frontend: `components/admin/sources/WaitInfo.tsx` — "Holat" ustunida (yoqilgan, oxirgi urinish xato bo'lsa):
  sabab + HTTP kodi (masalan "So'rovlar cheklangan · HTTP 429"), "Sayt 5 daq kutishni so'radi (Retry-After)"
  (Telegram — FloodWait), "Qayta urinish 31 daq dan keyin" — har soniya yangilanadi, ustiga olib borilsa aniq vaqt;
  muddat 45 s dan oshsa satr API'dan qayta o'qiladi. Tarix paneli va "Hozir ishga tushirish"/"Sinash" natijasida ham
  "Sayt so'ragan kutish" / "Keyingi urinishgacha". i18n: `adminSources.wait.*`, `runs.retryAfter|wait` (911 kalit × 4).
- Testlar: `test_scheduler.py` — bloklash parametrlari `last_outcome`/`wait_seconds`/`retry_after_seconds` bilan,
  yangi `test_rate_limit_wait_visible_then_cleared` (429 + Retry-After 300 → API → muvaffaqiyatda tozalanadi).
- Admin PATCH: oraliq **qisqarsa** keyingi urinish yangi oraliqqa tortiladi (avval eski uzun reja kutilardi), lekin
  `last_check_at + retry_after_seconds` dan oldin emas; uzaysa — reja o'zgarmaydi. Test: `test_admin_sources.py`.
- NewsNow (id 123) — admin API orqali **yoqildi**, foydalanuvchi talabi bilan oraliq **60 s** (jitter 20%;
  bloklansa backoff + Retry-After, endi panelda ko'rinadi). Birinchi urinish (14:28 UTC): HTTP 200, kartochka yo'q →
  xato. Ulagichga zaxira tahlil (kartochka belgilari bo'lmasa — `/A/<id>` havolalari, ota elementdan nashr/vaqt) va
  xatoga tashxis (`fingerprint`: hajm, `<title>`, `<article>`/`article-card`/`/A/` soni, `<script>`) qo'shildi.
  Keyingi urinish (14:46): 100 element o'qildi, 58 hodisa (baseline) — hammasida nashr va vaqt; kategoriyalar:
  other 26, leak 10, advisory 6 ... Events'da **Global** filtrida ko'rinadi.

### v2 dan keyin — NewsNow ulagichi (2026-11-16)
- Foydalanuvchi talabi: NewsNow'dan yangiliklar olish. Berilgan `newsnow/` papkasida dastur kodi yo'q — faqat boshqa
  loyihaning `pg_dump` nusxasi (2448 sarlavha, 2026-08-07…09-07, asl havola/matn yo'q). Papka `.gitignore` da; dump
  lokal alohida konteynerda: `cd newsnow && docker-compose up -d` (PostgreSQL 17, `127.0.0.1:5433`, parol
  `newsnow/.env`). Platformaga import qilinmadi (`EVENTS_SINCE` dan eski).
- NewsNow robots.txt: `anthropic-ai` (AI botlari) — butun sayt yopiq; `User-agent: *` uchun mavzu sahifalari ochiq,
  `?p=` sahifalash, `/A` (maqolaga o'tish), `/cgi`, `/share` ... yopiq. Sahifa tuzilishi foydalanuvchi brauzerda
  saqlagan sahifadan o'rganildi (Claude saytga kirmadi).
- `connectors/newsnow.py` (`kind=newsnow`, `config.url`): faqat newsnow.com / newsnow.co.uk, https, so'rov qatorisiz,
  yopiq yo'llar taqiqlangan, boshqa xostga redirect — xato. `article.article-card` → sarlavha, nashr
  (`<nashr> (NewsNow)`), `data-timestamp`, havola `c.newsnow.com/A/<id>?...` (saqlanadi, platforma unga kirmaydi),
  `extra.publisher_country`. Takror kaliti `newsnow:<id>` — havola qo'shimchasi ochilishlar orasida o'zgarsa ham
  bitta hodisa. Kartochka topilmasa — `ConnectorError` (challenge — `SourceBlocked`), jim `ok` emas.
- Migratsiya `0012_newsnow_source`: "NewsNow: Cyber Attacks" (`/us/Tech/Cyber+Security/Cyber+Attacks`) — **o'chiq**
  (`disabled`; yoqish — admin qarori), `scope=global` (Events standart ko'rinishi regional — toza qoladi), faqat
  kiber filtri, 30 daq, en, tarjima yoqiq. Saqlangan sahifada: 66 maqola → kiber filtrdan 43; ~9 tasi leak/ransomware
  (🔔 ham beradi). Faqat Markaziy Osiyo kerak bo'lsa — hudud filtri (o'sha sahifada 0).
- Testlar: `test_connector_newsnow.py` (21; fixture — saqlangan sahifadan 4 kartochka) + seed soni 78 → 79
  (`test_admin_sources`, `test_data_model`); migratsiya/scheduler/admin/html_list/followups to'plami ✅.

### v2 dan keyin — Telegram "Arxiv" papkasidagi kanal/guruhlar (2026-11-16)
- Foydalanuvchi talabi: *"telegramdagi archive chats dagi barcha kanal va guruhlarni ham monitoring qilsin"*.
- Avval: yig'uvchi faqat `TG_CHATS` dagi 22 chatni (har biri alohida manba, 0006 migratsiyasi) o'qirdi; dialoglar
  `iter_dialogs(limit=TG_DIALOG_LIMIT)` bilan — arxiv alohida so'ralmasdi.
- `telegram_user.py`: `iter_chat_dialogs()` — asosiy ro'yxat (folder 0, `TG_DIALOG_LIMIT`) + Arxiv (folder 1,
  `TG_ARCHIVE_LIMIT=500`), takrorsiz; `ChatInfo.archived`; `list_archived_chats()`; `_dialog_map` arxivni ham ko'radi
  (arxivdagi chat manbasi "topilmadi" bo'lmaydi). `GET /api/telegram/chats` → `archived` maydoni.
- `services/events/telegram_archive.py`: `TG_MONITOR_ARCHIVED=true` bo'lsa housekeeping'da (muvaffaqiyatdan keyin
  soatiga bir; sessiya yo'q bo'lsa 10 daqiqada qayta) arxivdagi har kanal/guruh uchun `telegram_user` manbasi:
  `Telegram: <nom> [<kalit>]`, 0006 bilan bir xil sozlama (10 daq, ochiq kanal — tarjima yoqiq, yopiq — o'chiq),
  `state.origin = "archive"`. Mavjud manba (username yoki ID bo'yicha, o'chirib qo'yilgani ham) tegilmaydi.
  Kalit so'z filtri (`TG_UZ_FILTER`, `TG_EXTRA_KEYWORDS`) boshqa Telegram manbalari bilan bir xil.
- `backend/.env`: `TG_MONITOR_ARCHIVED=true` (nusxa `.env.bak-*`); `.env.example` — `false` + izoh.
- Jonli: Telegram sessiyasi endi ulangan; arxivda 28 chat (15 kanal, 13 guruh) — 21 tasiga yangi manba, 7 tasi
  `TG_CHATS` da bor edi; 28/28 qamrab olingan. Sinov: ochiq kanal va yopiq guruh manbalari — `ok`, xabarlar o'qildi
  (`last_id` saqlandi), filtrdan o'tgani 0. ⚠️ Telethon sessiya fayli (SQLite) backend jarayonida band — ikkinchi
  jarayondan `get_client()` qilmang (`database is locked`), tekshiruv — `/api/telegram/*` orqali.
- Testlar: `test_telegram_archive.py` (2) + Telegram/manbalar testlari — 85 ✅.

### v2 dan keyin — frontend Docker'da, qayta yoqilganda avtomatik; LAN qaytarildi (2026-11-16)
- Foydalanuvchi talabi: platforma faqat tailnet'dan `https://<mashina>.<tailnet>.ts.net` da ochilsin (Serve, Funnel
  emas); LAN va internetdan 3000/8000 yopiq; localhost ishlab chiqish uchun qoladi. Reja: 1) Tailscale o'rnatish va
  `tailscale up --operator=$USER --hostname=<nom>` (foydalanuvchi o'zi, sudo; login URL'ni o'zi ochadi; sertifikatdan
  oldin nom tasdiqlanadi — CT loglariga tushadi); 2) 127.0.0.1 ga bog'lash; 3) `tailscale serve --bg`: `/` → :3000,
  `/api` → :8000/api (prefiks kesilishi curl bilan tekshiriladi); 4) `NEXT_PUBLIC_API_URL`, `CORS_ORIGINS`,
  `CORS_ALLOW_LAN=false`, `TRUSTED_PROXIES=172.18.0.1` (Docker gateway — X-Forwarded-For); 5) ufw (o'chiq; 22-port
  tegilmaydi); 6) yoqilganda avtomatik ishga tushish.
- ✅ 2-qadam: `docker-compose.yml` backend `127.0.0.1:8000:8000`; `package.json` `next dev|start -H 127.0.0.1`;
  `.env.example` va README LAN o'rniga reverse proxy / Tailscale.
- ✅ 6-qadam (foydalanuvchi OK berdi): compose'da `restart: unless-stopped` (db, backend; mavjud konteynerlarga
  `docker update` bilan ham), yangi `frontend` xizmati — `frontend/Dockerfile` (standalone; `NEXT_PUBLIC_API_URL`
  build arg — loyiha ildizidagi `.env` dan, `.env.local` image'ga kirmaydi; `HOSTNAME=0.0.0.0`, `USER node`,
  `public/` yo'q bo'lsa yaratiladi), port `127.0.0.1:3000:3000`. `docker.service` yoqilgan → qayta yoqilganda ko'tariladi.
- ✖ 1, 3, 4, 5-qadamlar (Tailscale o'rnatish, Serve, ts.net env, ufw) — **bekor**: foydalanuvchi *"menga tailscale ni
  OS dan o'chirish kerak edi, bo'ldi"*. Tailscale kompyuterda yo'q (paket, xizmat, apt manbasi, `tailscale0` — tekshirildi).
  Natija: platforma faqat shu kompyuterdan (localhost); LAN'dan ochish kerak bo'lsa — portlarni `0.0.0.0` ga qaytarish
  (`docker-compose.yml` 3000/8000, `backend/.env` da `CORS_ALLOW_LAN=true` allaqachon bor).
- Keyin foydalanuvchi LAN'ni qaytarishni tanladi: compose `0.0.0.0:3000` va `0.0.0.0:8000`, `next dev|start -H 0.0.0.0`;
  5432 — `127.0.0.1`. Frontend Docker'da va `restart: unless-stopped` qoldi.
  ⚠️ docker-compose 1.29: `up -d backend` `db` konfiguratsiyasi o'zgargani (`restart`) uchun db'ni ham qayta yaratdi va
  `KeyError: 'ContainerConfig'` bilan to'xtadi — eski db `<hash>_osint_db_1` nomida qoldi. Tuzatish: ma'lumot
  `osint_postgres-data` volume'da ekanini tekshirib, `docker rm <hash>_osint_db_1 && docker-compose up -d db backend`.
  Tekshirildi: ✅ ma'lumot joyida (users/events/sources), LAN IP orqali 3000/8000 — 200, 5432 — yopiq, CORS LAN — ruxsat,
  begona — rad; smoke LAN IP orqali (16 sahifa × desktop/360px) — toza.

### v2 dan keyin — API kalitlari tekshiruvi (2026-11-16)
- Foydalanuvchi `backend/.env` ga kalitlarni kiritdi; konteyner qayta yaratildi, kalitli manbalar dry-run qilindi:
  `RANSOMWARE_LIVE_API_KEY` ✅ (200), `OTX_API_KEY` ✅ (200), `CLOUDFLARE_API_TOKEN` ✅ (`/user/tokens/verify` — active),
  `ABUSECH_AUTH_KEY` ❌ — abuse.ch javobi `unknown_auth_key` (kalitning o'zi tanilmadi; auth.abuse.ch dan qayta olish kerak),
  `NVD_API_KEY` — bo'sh (ixtiyoriy; kalitsiz NVD vaqt tugashi bilan javob berdi).
- Tuzatildi: Cloudflare Radar API endi faqat `dateStart` bilan 400 qaytaradi ("The dateEnd must be after dateStart") —
  `cloudflare_radar.py` `dateEnd=now` ham yuboradi (test qo'shildi).
- Kalitli manbalar (86, 90–92, 94, 95) hali **o'chiq** (`enabled=false`) — yoqish admin → Manbalar.
- Eslatma: `.env` dagi kalit o'zgarsa backend konteynerini **qayta yaratish** kerak (`stop && rm -f && up -d`):
  `env_file` qiymatlari `os.environ` da qoladi va `api_key_for` ularni `.env` faylidan ustun qo'yadi.

### v2 dan keyin — "Ўзбекча" interfeysi va `translit_uz` → jaybi dvigateli (2026-11-16)
- Foydalanuvchi talabi: *"ikkalasini ham jaybi dvigateliga o'tkaz"* — (a) eski `translit_uz` o'rniga latin.jaybi.uz
  dvigateli; (b) interfeysda o'zbek kirill tili.
- (a) `text.py`: `translit_uz` olib tashlandi; worker (`plan_rows`, `_fix_uz`) — `uz_to_latin` (сентябрь → sentabr,
  объект → obyekt, ШАҲАР → SHAHAR — eski funksiya "Sentyabr/Ob'ekt/ShAHAR" berardi).
- `uz_to_cyrillic` endi himoyalangan: URL / e-mail / @username, `{placeholder}`, `<code>…</code>` va `` `kod` ``, teglar,
  fayl yo'li va domenlar (`backend/.env`, `kun.uz`), harf+raqam (5G, CVE-2026-1234), qisqartmalar (API, OSINT, UZCERT;
  bosh harfli so'z 6 harfgacha), CamelCase (RansomLook), o'zbek lotinida yo'q harfli so'zlar (`c` — "ch" dan tashqari,
  `w`: Cybercab, Facebook, Twitter) va `KEEP_LATIN` ro'yxati (Google, username, backend, ransomware…) lotinda qoladi.
  O'zbekcha qisqartmalar (`UZ_ABBREVIATIONS`: IIV → ИИВ, BMT, AQSh → АҚШ…) va apostrofli bo'laklar (ID'si → ID'си,
  O'ZBEKISTON) kirillga; so'zlar orasidagi `/` — yo'l emas (ko'rsatish/yashirish → кўрсатиш/яшириш).
- (b) Til `uz-Cyrl` ("Ўзбекча"):
  - Backend: `core/i18n.py` — `UZ_CYRL`, `DISPLAY_LANGS`; `Accept-Language: uz-Cyrl[-UZ]`; `t(code, "uz-Cyrl")` uz
    shablonini o'giradi (parametr qiymatlari tegilmaydi). `/api/events|notifications|stats/latest?lang=uz-Cyrl` —
    o'zbekcha matn kirillga (`display_lang = "uz-Cyrl"`, `translated` o'zgarmaydi); o'zbekcha tarjimasi yo'q hodisa —
    asl matn. Kategoriyalar: `name_uz_cyrl` / `description_uz_cyrl` (hisoblanadi, bazada yo'q). `users.locale` — `uz-Cyrl`.
  - Frontend: `LOCALES = uz, uz-Cyrl, ru, en`; `messages/uz-Cyrl.json` **generatsiya**:
    `python3 backend/scripts/gen_uz_cyrl_messages.py` (ICU plural/select ichidagi matn o'giriladi, kalitlar va `{arg}` —
    yo'q; `--check` — eskirganmi; `npm run test:i18n` ham tekshiradi). Oy/hafta kunlari kirillda (`lib/format.ts`,
    `widgets.tsx`), `isUzbek()`, `categoryText()`.
  - Til tanlagichda har til o'z nomida (O'zbekcha / Ўзбекча / Русский / English) — ru'dagi uzun nomlar
    ("Узбекский (латиница)") 360px da sahifani 50px kengaytirardi.
- Jonli: `/api/events?lang=uz-Cyrl` → "Ўзбекистонда ИИВ ва банклар иштирокида 24/7 режимида…", "Тесла … \"Cybercab\"";
  kategoriyalar "Маълумотлар сизиб чиқиши", "Фишинг"; xato matni "Аутентификация талаб қилинади".
- Tekshirildi: ✅ `test_uz_cyrillic_ui.py` + `test_uztranslit_vendor.py` + `test_translations.py` (57), qoidalar
  tuzatilgach `test_uz_cyrillic_ui` + `test_translations` + `test_followups` + `test_translator_nllb` (117); smoke `uz-Cyrl`
  LAN orqali — 16 sahifa × desktop/360px toza; ochiq sahifalar uz/uz-Cyrl/ru/en × 360px toza; `tsc`; `test:i18n`
  (905 kalit × 4 til, generator dolzarb).

### v2 dan keyin — LAN'dan kirish (2026-11-16)
- Foydalanuvchi talabi: platforma LAN'da `http://<LAN-IP>:3000` da ochilsin, localhost ham ishlasin.
- Frontend: `npm run dev` → `next dev -H 0.0.0.0` (`start` ham `-H 0.0.0.0`). API manzili bitta joyda —
  `frontend/lib/config.ts` (`api.ts`, `adminApi.ts`, `statsApi.ts` dagi qattiq `localhost:8000` olib tashlandi):
  `NEXT_PUBLIC_API_URL`, bo'sh bo'lsa — sahifa ochilgan host'ning 8000-porti. `frontend/.env.local` da LAN IP
  (git'da yo'q), `.env.example` da bo'sh qiymat va misol.
- Backend: konteyner ichida uvicorn allaqachon `0.0.0.0`; compose porti `127.0.0.1:8000` → `0.0.0.0:8000`.
  PostgreSQL porti `127.0.0.1:5432` da qoldi. `backend/.env` → `CORS_ORIGINS` ga LAN origin qo'shildi (nusxa
  `.env.bak-*`); kod standarti (`http://localhost:3000`) o'zgarmadi.
- ⚠️ `0.0.0.0` — kompyuterning barcha tarmoqlari: LAN va VMware tarmoqlari ham. API'ni internetga
  ochish kerak bo'lsa — reverse proxy + HTTPS (`TRUSTED_PROXIES`). Token `localStorage` da — har origin uchun alohida
  login kerak (localhost va LAN IP).
- Tekshirildi: ✅ `0.0.0.0:3000` va `0.0.0.0:8000` tinglaydi, 5432 — faqat 127.0.0.1; `/health` localhost va LAN IP'da;
  CORS preflight: localhost:3000 va LAN:3000 — ruxsat, begona origin — yo'q; bundle'da API = LAN IP; smoke LAN orqali
  (analyst, 13 sahifa × desktop/360px) — toza; `tsc`.
- Keyin (foydalanuvchi: *"lokalda boshqa komplar ko'radigan qilib ber"*): manzil IP'ga bog'liq bo'lmasin —
  `CORS_ALLOW_LAN=true` (`config.LAN_ORIGIN_RE`: localhost, 127.0.0.1, 10/8, 172.16/12, 192.168/16, Tailscale 100.64/10,
  bir so'zli / `.local` nom — faqat `:3000`; `allow_origin_regex`), `frontend/.env.local` da `NEXT_PUBLIC_API_URL=` bo'sh
  (API = sahifa host'i:8000). ufw o'rnatilgan, lekin yoqilmagan (`ENABLED=no`) — port bloklanmagan.
  Frontend sessiyadan mustaqil ishga tushirildi: `setsid nohup npm run dev > frontend/dev.log` (to'xtatish:
  `pkill -f "next dev"`). ⚠️ Kompyuter qayta yoqilsa frontend o'zi ko'tarilmaydi (backend/db — `docker-compose start`).
  Tekshirildi: CORS — localhost / LAN / Tailscale / `pc.local` :3000 ruxsat, begona va boshqa port — rad; smoke
  LAN IP va Tailscale IP orqali — toza; `test_lan_origin_regex` (15 holat).
- Keyin (foydalanuvchi: *"tailscale ni o'chir, VPN'ni tag-tugi bilan"*): Tailscale kompyuterdan olib tashlanadi —
  `LAN_ORIGIN_RE` dan Tailscale/CGNAT `100.64/10` oralig'i chiqarildi (test: `100.67.104.58` endi rad). Tizimdan
  o'chirish `sudo` talab qiladi — foydalanuvchi o'zi bajaradi (`tailscale logout`, `apt purge tailscale
  tailscale-archive-keyring`, `/var/lib/tailscale`, apt manbasi va kalit).

### v2 dan keyin — o'zbek kirill (`uzn_Cyrl`) latin.jaybi.uz dvigateli bilan (2026-11-16)
- Foydalanuvchi talabi: *"uzn_Cyrl ni latin.jaybi.uz dan foydalangan holda lotindan kirillga o'tsin"*.
- latin.jaybi.uz — server API'siz (brauzerda, WASM). Uning dvigateli ochiq: `github.com/kool277/uz-latn-kiril` (MIT,
  Copyright (c) 2026 jaybi.uz). Rasmiy Python porti `core/python/uztranslit.py` v1.3.0 (commit `ba20af5`) **o'zgartirishsiz**
  `backend/app/services/i18n/vendor/` ga ko'chirildi (+ `LICENSE.uztranslit`, `README.md`: manba, commit, SHA-256,
  yangilash tartibi). Faqat `re`; tarmoqqa chiqmaydi — sayt bilan bir xil qoidalar (ye/e, ts → ц, yo'l → йўл,
  o'zlashma so'zlar lug'ati: obyekt → объект, iyul → июль, 15-iyuldagi → 15-июлдаги; URL / e-mail / @username tegilmaydi).
- `text.py`: `uz_to_cyrillic()` (lotin 1995/2026 → kirill), `uz_to_latin()` (kirill → lotin, ASCII `'`).
- `translator.py`: `uz-Cyrl` / `uzn_Cyrl` kodlari (NLLB kodlarining o'zi ham qabul qilinadi) → model `uzn_Latn`; maqsad
  kirill bo'lsa tarjima lotinda olinib kirillga o'giriladi; manba kirill — avval lotinga (endi `translit_uz` o'rniga
  jaybi dvigateli); o'zbek ↔ o'zbek (`uz` ↔ `uz-Cyrl`) — servissiz, faqat yozuv; boshqa bir xil til juftlari — o'zgarishsiz.
- Platformaning saqlanadigan tillari o'zgarmadi (en/ru/uz-lotin); `plan_rows` va worker'dagi `_fix_uz` hali `translit_uz`
  ishlatadi (alohida qaror: ularni ham jaybi dvigateliga o'tkazish / UI'da o'zbek kirill ko'rinishi). → Bajarildi:
  yuqoridagi "Ўзбекча" interfeysi yozuvi.
- Testlar: `tests/test_uztranslit_vendor.py` — yuqori oqim conformance to'plami (224 case, 10 roundtrip, 9 detect,
  3 optional; `tests/fixtures/uztranslit_fixtures.json`, guruhlab — to'plamni sekinlatmaslik uchun) + o'ramlar;
  `test_translator_nllb.py` — `uzn_Cyrl` maqsad/manba, servissiz yozuv almashtirish, kod jadvali.
- Jonli: ru → `uzn_Cyrl` "Хакеры атаковали аккаунты президента Азербайджана в социальных сетях" →
  "Озарбайжон президентининг ижтимоий тармоқлардаги аккаунтларига хакерлар ҳужум қилди".
- Tekshirildi: ✅ vendor conformance + klient + tarjima testlari 65/65; jonli ru → uzn_Cyrl. To'liq to'plam — keyingi yozuvda.

### v2 dan keyin — tarjima servisi: Google → o'z NLLB servisi (2026-11-16)
- **Provayder**: Google Cloud Translation olib tashlandi (`GOOGLE_TRANSLATE_API_KEY` kod, `.env.example`, joriy hujjatlardan;
  tarixiy yozuvlarda izoh bilan qoldi). Yangi: `TRANSLATE_API_URL` (standart `https://translate.deepcore.uz`, kalitsiz,
  `facebook/nllb-200-3.3B`, cuda), `TRANSLATE_TIMEOUT_SECONDS=30`; `TRANSLATE_MONTHLY_CHAR_LIMIT` standarti endi **0 =
  chegarasiz** (hisob yuritiladi; admin kartochkasida "chegarasiz", progress bar yashiriladi).
- **Klient** `services/i18n/translator.py` → `NllbTranslator` (interfeys o'zgarmadi: `translate(texts, source, target)`,
  `configured`, `name`): ISO → FLORES-200 (`uz→uzn_Latn, ru→rus_Cyrl, en→eng_Latn, kk→kaz_Cyrl, ky→kir_Cyrl,
  tg→tgk_Cyrl, tk→tuk_Latn`, hammasi `GET /languages` bilan tekshirilgan). ⚠️ Servisda **`uzn_Cyrl` yo'q** — o'zbek
  kirill matni `translit_uz` bilan lotinga o'girilib `uzn_Latn` sifatida yuboriladi. Manba tili avvaldan ham aniq
  beriladi (`detect_lang`), Google avto-aniqlashiga tayanilmagan edi — yangi aniqlagich kerak bo'lmadi.
  `/translate/batch` ≤ 64 matn; `max_input_length` (`GET /model`, 512 token, bir marta keshlanadi) − 8 belgidan uzun
  matn gaplar bo'yicha bo'linadi va qayta birlashtiriladi. Ulanish xatosi / 5xx — 2 marta qayta urinish (1 s, 2 s +
  jitter); timeout (GPU yukini takrorlamaslik uchun), 422 (`detail[].loc/msg` bilan aniq xato) va noma'lum til — yo'q;
  429 → `RateLimited`. `translate_or_original()` — navbatdan tashqari chaqiruvlar uchun (warning + asl matn).
- **Navbat** (`worker.py`): xatoda klient istisno ko'taradi → qator `pending`, warning logi, 3 urinish (asl matn
  tarjima sifatida keshga yozilmaydi — foydalanuvchi bilan kelishildi); 422 / noma'lum til → darhol `failed`; har
  qatorga o'z xatosi; provayder nomi `translator.name` (`nllb`).
- **HTTP**: tarjima uchun alohida `HttpFetcher` (`scheduler.state._tr_http`) — SSRF filtri yo'q (URL operator
  sozlamasi) va `pause_range=(0, 0)` (yangi parametr; ulagichlar uchun 1–4 s pauza o'zgarmadi).
- Testlar: `tests/test_translator_nllb.py` (27 holat: kodlar, 64 lik bo'lish, uzun matn, kirill o'zbek, bo'sh matnlar,
  noma'lum til, 422, 5xx qayta urinish/taslim, ulanish xatosi, timeout, 429, `/model` ishlamasa, fallback, worker:
  pending / darhol failed / 0 = chegarasiz, scheduler fabrikasi); Google testlari olib tashlandi; conftest testlarni
  haqiqiy servisdan ajratadi (`translate_api_url=""`).
- Jonli: backend qayta ishga tushgach navbat o'zi ishladi — 9 so'rovda 98 qator `nllb` (29 465 belgi), xatosiz;
  namunalar ru→en/uz, uz→en/ru to'g'ri (bitta ru→en sarlavhada "В Ташкенте" tushib qolgan — NLLB xususiyati).
  `/health` → ok/cuda; `/translate` "Toshkentda kiberjinoyatchilar qo'lga olindi." → "В Ташкенте были задержаны
  киберпреступники.".
- `backend/.env`: avval qo'shilgan bo'sh `GOOGLE_TRANSLATE_API_KEY=` qatori olib tashlandi (nusxa `.env.bak-*`);
  `TRANSLATE_*` qatorlari shart emas (standartlar).
- Tekshirildi: ✅ backend **314 pytest** (to'liq to'plam, 19.5 daq, xatosiz); ✅ `tsc`, i18n 904 kalit × 3 til.

### v2 dan keyin — kichik ishlar (2026-11-16)
"Keyingi qadamlar" 4-bandidan (Next 15 ga ko'chish — alohida ish, qilinmadi):
- **Events davri soat aniqligida**: `GET /api/events?range=24h|7d|30d|90d` (hozirdan orqaga). Ilgari "24 soat" tugmasi
  `date_from=kecha` yuborardi — kecha kun boshidan, ya'ni 24–48 soat ko'rsatardi. `date_from`/`date_to` berilsa `range`
  e'tiborsiz (statistika bilan bir xil qoida); `RANGES` endi `api/events.py` da, `stats_v2` undan oladi.
  Frontend: Events tez tugmalari `range` yozadi (chip "Davr: 24 soat"), qo'lda sana tanlansa `range` olib tashlanadi;
  dashboard → Events havolasi ham `range` uzatadi (ilgari kunga yaxlitlanardi).
- **Proxy ortida mijoz IP'si**: `TRUSTED_PROXIES` (IP/CIDR, vergul bilan; noto'g'ri qiymat — ishga tushishda xato).
  Faqat ishonchli proxy'dan kelgan so'rovda `X-Forwarded-For` o'qiladi: zanjir o'ngdan, ishonchli hop'lar o'tkaziladi,
  birinchi ishonchsiz manzil — mijoz; buzilgan zanjirda proxy IP'si. Bo'sh (standart) — sarlavha e'tiborsiz.
- **Tarix hisoblagichi**: `GET /api/search/history/counts` → `{total, by_kind}`; tarix sahifasi endi butun
  `/api/stats/overview` ni (hodisalar bo'yicha 5 ta so'rov) chaqirmaydi. Ishlatilmay qolgan `frontend/lib/stats.ts`
  o'chirildi (backend'dagi v1 `/api/stats/overview` endpoint'i saqlandi).
- Testlar: `tests/test_followups.py` — range (23s/25s chegarasi, sana ustunligi, 422), `client_ip` 11 holat
  (soxta chap hop, ichki zanjir, bir nechta sarlavha, port, IPv6, buzilgan zanjir), sozlama validatsiyasi, proxy ortida
  login limiti mijoz bo'yicha, tarix sonlari (begona foydalanuvchi hisoblanmaydi, 401).
- Tekshirildi: ✅ jonli API (`range=24h` → 4, `7d` → 53); ✅ brauzerda preset → URL/chip/aria-pressed, chip'ni olib
  tashlash, `?range=7d` to'g'ridan-to'g'ri, dashboard havolalari `range=24h`, tarix sahifasi; ✅ smoke 26/26
  (desktop + 360px); ✅ `tsc`; ✅ backend **288 pytest** (to'liq to'plam, xatosiz).

### v2 — Bosqich 9: mustahkamlash va topshirish (2026-11-15)
- **Rate limiting** (`core/ratelimit.py`, jarayon xotirasida, sirpanuvchi oyna; Redis yo'q): login — IP bo'yicha 20 va
  email bo'yicha 10 urinish / 15 daq; tekshiruvlar (`/api/search/*`) — foydalanuvchiga 30 / daq; `POST /api/events/refresh`
  — 5 / 10 daq; manbani "hozir yig'ish" — 30 / 10 daq. Oshsa: 429, `Retry-After`, `code: too_many_requests` (3 tilda).
  Sozlamalar `.env` da (`RATE_LIMIT_*`, `LOGIN_RATE_*`, `SEARCH_RATE*`, `REFRESH_RATE*`).
- Events qidiruvida `%` va `_` ekranlanadi (Bosqich 4 da qilingan, testi bor).
- **QA hisobi o'chirildi**: `test@example.com` bazadan o'chirildi (35 ta QA qidiruvi bilan; nusxa
  `~/osint-backups/osint-pre-phase9-20261115-011527.sql`), parol hujjatlardan olib tashlandi. ⚠️ Parol git tarixida
  qolgan (repo ochiq) — hisob endi mavjud emas, shuning uchun parol yaroqsiz. Testlar o'z foydalanuvchilarini yaratadi;
  smoke uchun `backend/scripts/qa_token.py --role admin|analyst [--delete]` (parolsiz, qisqa muddatli JWT).
  `.claude/agents/qa-tester.md` yangilandi.
- Testlar: `tests/test_ratelimit.py` — sirpanuvchi oyna, login (email/IP), tekshiruvlar va refresh limitlari, o'chirish;
  **har bir admin route** (`app.routes` dan avtomatik yig'iladi, 30+) analyst uchun 403 `admin_only`, tokensiz 401.
  Qolgan talab qilingan testlar oldingi bosqichlarda: klassifikator (Bosqich 4), rejalashtiruvchi — jitter, backoff,
  baseline (Bosqich 2), sog'liq holatlari (2), tarjima navbati soxta provayder bilan (5), statistika (8),
  migratsiyalar base↔head vaqtinchalik bazada (0).
- Hujjatlar: `README.md` (v2: imkoniyatlar, ishga tushirish, kalitlar jadvali, migratsiya va orqaga qaytarish, testlar),
  `docs/architecture.md` (kategoriyalar, tarjima, statistika, admin API, xatolar, rate limiting, rollar),
  `backend/.env.example` (APP_TIMEZONE, SOURCE_DOWN_ALERT_HOURS, rate limit, eski sozlamalar izohi), `docs/tasks.md`.
  Ishlatilmay qolgan `EVENTS_POLL_SECONDS` sozlamasi olib tashlandi.
- Maxfiy qiymatlar tekshiruvi: `backend/.env` dagi SECRET_KEY / TG_API_ID / TG_API_HASH na kuzatiladigan fayllarda, na git
  tarixida yo'q; `.env` va `*.session` git'da emas.
- Tekshirildi: ✅ backend **273 pytest** (to'liq to'plam, 16.5 daq); ✅ jonli: rate limit bilan backend qayta ishga tushdi;
  ✅ smoke — analyst tokeni (qa_token) bilan dark/en barcha sahifalar 26/26, admin bilan light/ru 28/28, Bosqich 8 dagi
  matritsa 108/108; ✅ `tsc`, production build, i18n (903 kalit × 3 til), kontrast.
- ⚠️ Tekshirilmadi: bir nechta uvicorn worker (rate limit va advisory lock bitta jarayon uchun mo'ljallangan — README'da);
  proxy ortida ishlaganda haqiqiy mijoz IP'si (`X-Forwarded-For` hozir o'qilmaydi).

### v2 — Bosqich 8: interaktiv statistika dashboard'i (2026-11-15)
- **Backend** (`api/stats_v2.py`, commit f04c7ef da kiritilgan): hamma endpoint `/api/events` bilan bir xil filtrlar +
  davr (`range` = 24h | 7d | 30d | 90d yoki `date_from`/`date_to` Toshkent kuni); oldingi davr — xuddi shu uzunlikdagi.
  `GET /api/stats/kpis` (jami va o'zgarish %, kritik+yuqori, ransomware, davlatlar, manbalar, bir necha manbada),
  `/timeseries` (`bucket` hour|day|week|month — `APP_TIMEZONE`=Asia/Tashkent bo'yicha; `group_by` category|country|source|
  channel|severity; bo'sh bo'laklar 0; top-N + `__other__`, davlatsiz — `__none__`), `/breakdown` (category, country,
  source, channel, severity, actor, sector), `/heatmap` (hafta kuni × soat), `/source-health`, `/latest` (≥ high,
  `?lang=`). `0011_stats_indexes`: `coalesce(published, first_seen)`, severity, channel, (scope, vaqt).
  Eski `/api/stats/overview` qoldi — faqat tarix sahifasidagi qidiruvlar soni uchun (tekshiruv modullariga tegilmadi).
- **Frontend** (`/dashboard`): bitta filtr paneli (davr, kategoriya, davlat, kanal, manba, jiddiylik, qamrov) — URL'da;
  faol filtr chiplari, "Hammasini tozalash", "Shu filtrlar bilan hodisalar" (Events'ga o'tish). Kesishma filtr: ustun,
  qator, segment yoki legenda bosilsa filtr qo'shiladi. Vidjetlar: asosiy ko'rsatkichlar (oldingi davrga nisbatan),
  vaqt bo'yicha (kategoriyalar bo'yicha yig'ilgan, zoom), kategoriyalar, davlatlar, jiddiylik trendi, hafta×soat issiqlik
  xaritasi, eng faol manbalar, ransomware guruhlari, nishondagi sohalar, so'nggi muhim hodisalar, manbalar sog'lig'i.
  Har vidjetda: tooltip, jadval ko'rinishi, CSV, yashirish; "Vidjetlarni sozlash" — ko'rsatish/yashirish va tartib
  (localStorage'da). Har 60 s yangilanadi, yashirin tabda to'xtaydi. Bo'sh vidjet — halol bo'sh holat.
- ECharts 6.1: `lib/echarts.ts` (Bar, Line, Heatmap + Grid/Tooltip/Legend/DataZoom/VisualMap/Aria, SVG), dinamik import —
  ~700 KB alohida bo'lak, faqat dashboard'da; `/dashboard` birinchi yuklanish 136 kB. Palitra dataviz validatoridan o'tdi
  (tafsilot: `docs/design-system.md` → Grafiklar); 8 rangdan ko'p emas (barqaror 7 kategoriya + "Boshqa").
  Eski `ColumnChart`/`HBarList` olib tashlandi.
- Tekshirildi: ✅ 7 stats testi (KPI va oldingi davr, top va "Other", davlat bo'yicha (bitta hodisa ikki davlatda) va
  `__none__`, soatlik bo'laklar, **Toshkent kuni** (20:30 UTC → ertangi kun), breakdown actor/sector/limit, heatmap,
  source-health, latest, 401); ✅ jonli API; ✅ brauzerda: light/en va dark/ru/uz — 11 vidjet haqiqiy ma'lumot bilan,
  konsol xatosiz, kesishma filtr URL'ga yoziladi, jadval ko'rinishi (31 qator), yashirilgan vidjet qayta yuklashda
  eslab qolinadi, 360px'da skrollsiz; ✅ `tsc`, production build; ✅ smoke matritsasi 108/108
  (dashboard ham: light/dark × uz/ru/en × desktop/360px).
- ⚠️ Cheklov: Events sahifasi sanalari kun aniqligida — dashboard'dan "24 soat" bilan o'tilganda Events kechagi sanadan
  boshlab ko'rsatadi; vaqt grafigida zoom faqat ko'rinishni o'zgartiradi (filtrga aylanmaydi).

### v2 — Bosqich 7: admin bo'limi va Events sahifasi (2026-11-15)
- **Backend**: `GET|PATCH /api/admin/users` (rol admin/analyst, faollik; oxirgi faol adminni pasaytirish/o'chirish — 409
  `last_admin`); `admin_alerts` jadvali (`0010_admin_alerts`) — manba `SOURCE_DOWN_ALERT_HOURS` (3) soatdan beri
  down/blocked bo'lsa housekeeping bir marta ogohlantirish yaratadi, manba tiklanganda yopiladi; `/api/notifications`
  adminlarga `system` ro'yxatini qaytaradi (o'qilmaganlarga qo'shiladi); `GET /api/events/facets` — filtr paneli uchun
  manbalar, davlatlar, asl tillar, kanallar, jiddiylik, scope (soni bilan).
- **Frontend** (`lib/adminApi.ts` — tiplangan admin mijozi; `/dashboard/admin` qobig'i — faqat admin, tablar):
  - **Manbalar** (`/dashboard/admin/sources`): holatlar bo'yicha xulosa qatori (bosilsa filtr), filtrlar URL'da (status,
    kind, enabled, nom), jadval (tur, kategoriya, til, interval, holat + izoh, oxirgi muvaffaqiyat, kechikish, 24 soatlik
    elementlar, 7 kunlik uptime, keyingi yig'ish), kalit yo'q bo'lsa o'zgaruvchi nomi bilan ishora; "Sinash" (dry run:
    HTTP, kechikish, elementlar, filtrdan o'tganlar, 3 namuna), "Hozir yig'ish", tarix (xato matni bilan), yoqish/o'chirish
    (tasdiq bilan), o'chirish (hodisalar qolishi aytiladi), yaratish/tahrirlash paneli (ulagichning config maydonlari +
    "Advanced JSON", saqlashdan oldin sinash, server xatolari maydon yonida; `telegram_user` uchun akkaunt chatlaridan
    tanlash), JSON eksport/import.
  - **Kategoriyalar**: tartiblash (Up/Down, klaviatura), yaratish/tahrirlash (slug faqat yaratishda, nom/tavsif uz/ru/en,
    jiddiylik, 18 rang — nom va belgi bilan, ikon tanlash, notify, saqlash muddati, yoqilganlik), qoidalar muharriri
    (stem'lar tillar bo'yicha, pattern/exclude — har qator brauzerda tekshiriladi, weight, min_score), o'chirish
    ("Other" ga o'tadi), qayta tasniflash — avval dry run (o'tishlar jadvali, namunalar), keyin alohida "Qo'llash".
  - **Tizim**: yig'uvchi (lock, tsikl, urinishlar, holatlar → manbalar sahifasiga havola, 30 s da yangilanadi), tarjima
    (kalit yo'qligi tushuntiriladi, oylik belgilar, holat × til jadvali, xatolar, "Qayta urinish", "Navbatni ishlatish"),
    Telegram (sessiya bekor qilingan bo'lsa qayta login buyrug'i nusxalanadigan ko'rinishda), foydalanuvchilar (rol,
    faollik — tasdiq bilan, 409 xabari ko'rsatiladi).
  - **Events** qayta qurildi: filtr paneli — kategoriyalar, jiddiylik, davlatlar, kanal, manba (qidiriladigan), scope,
    asl til, sana (24 soat / 7 / 30 / 90 kun / ixtiyoriy), matn; hammasi URL'da (API bilan bir xil nomlar), faol filtr
    chiplari + "Hammasini tozalash", kartadagi kategoriya/jiddiylik/davlat/manba chipi bosilsa filtr qo'shiladi;
    adminlar uchun kartada "Kategoriyani o'zgartirish" (qayta tasniflashdan qulflanishi aytiladi); mobil — "Filtrlar (N)" paneli.
  - Qo'ng'iroq: adminlarga "Tizim" bo'limi (manba N soatdan beri ishlamayapti / bloklangan).
- 4 ta `ui-designer` subagent parallel (manbalar, kategoriyalar, tizim, Events); backend, API mijozi, admin qobig'i,
  qo'ng'iroq va integratsiya — asosiy sessiyada. Subagentlar haqiqiy manba/kategoriya/foydalanuvchini o'zgartirmadi —
  vaqtinchalik "QA test" obyektlarida sinab, keyin o'chirdi.
- Tekshirildi: ✅ backend testlar (users: ro'yxat, rol, oxirgi admin 409, 404; ogohlantirish: 4 soatlik down → 1 ta,
  takrorlanmaydi, analyst ko'rmaydi, tiklanishda yopiladi; fasetlar); ✅ `tsc`; ✅ i18n 825 kalit × 3 til;
  ✅ subagentlar brauzerda: manba yaratish → sinash → hozir yig'ish → tarix → tahrirlash → o'chirish; kategoriya
  yaratish/regex xatosi/tartib/o'chirish, qayta tasniflash dry run (57 hodisa, 0 o'zgarish); Events URL filtrlari
  (`?category=leak&severity=high,medium` → 6 hodisa, 3 chip; 360px skrollsiz); ✅ backend 235 pytest;
  ✅ smoke matritsasi 108/108 (6 asosiy + 3 admin sahifa × light/dark × uz/ru/en × desktop/360px), analyst bilan 28/28
  (admin sahifalari analyst'ga "faqat adminlar" holatini ko'rsatadi).
- Shu commitga Bosqich 8 uchun tayyorlangan statistika backend'i ham kirgan (`api/stats_v2.py`, `0011_stats_indexes`,
  `tests/test_stats.py`) — tafsilotlari Bosqich 8 yozuvida.
- ⚠️ Tekshirilmadi: Telegram chat tanlagich (sessiya bekor — 409 xabari ko'rsatiladi), JSON import brauzerda,
  "Kategoriyani o'zgartirish" haqiqiy hodisada (ataylab), Events sana filtri kun aniqligida ("24 soat" = kechagi sanadan).

### v2 — Bosqich 6: interfeys — Light / Dark / System, uz / ru / en (2026-11-15)
- Avval `docs/design-system.md` va `.claude/agents/ui-designer.md` qayta yozildi (faqat qorong'i / faqat o'zbekcha
  qoidalar olib tashlandi); `frontend.md`, `backend.md`, `database.md`, `osint-collector.md` v2 ga moslandi.
- **Tokenlar**: `app/globals.css` — `:root` (light) va `.dark` qiymatlari (bg, surface, surface-2, border, fg, fg-muted,
  fg-subtle, primary (yagona aksent), ring, success/warning/danger/info, chart-1..8); `app/tones.css` — 18 ta `.tone-*`
  (`scripts/gen-tones.mjs` Tailwind palitrasidan yaratadi); `tailwind.config.ts` tokenlarni bog'laydi, `darkMode: class`.
  `ink-*`, `slate-*`, `white/…`, `brand-*`, `dark:` — kodda qolmadi (grep bilan tekshirildi; istisno: `/report` qog'ozi
  ataylab yorug'). `scripts/contrast-check.mjs`: barcha token juftliklari va 36 tone ≥ 4.5:1 ikkala temada.
- **Tema**: `next-themes` (standart System, miltillashsiz), `ThemeToggle` (3 holat) yuqori panelda, login/register va
  landingda. Bezak olib tashlandi: aurora, to'r fon, radar, scramble/reveal, tilt/magnit/float, spotlight, sheen,
  harakatlanuvchi gradient, count-up; `framer-motion` bog'liqligi o'chirildi.
- **Til**: `next-intl` 4.15 (URL prefikssiz): `i18n/request.ts` — cookie `NEXT_LOCALE` → `Accept-Language` → uz;
  `users.locale` bilan sinxron (`LocaleSwitcher` → cookie + `PATCH /api/auth/me`; boshqa qurilmada tanlangan til kirishda
  qo'llanadi). `messages/{uz,ru,en}.json` — 349 kalit × 3 til (ICU ko'plik, rus tili one/few/many);
  `npm run test:i18n` kalitlar bir xilligini va ICU sintaksisini tekshiradi. `lib/format.ts` (`useFormat`) — o'zbekcha oy
  nomlari qo'lda, ru/en `Intl`, vaqt Toshkent zonasida. Kategoriya nomlari bazadan (`useCategories`), hodisa matni
  `?lang=` bilan interfeys tilida + "Asl matn" tugmasi; bildirishnomalar ham (`/api/notifications?lang=`).
- **Navigatsiya**: Umumiy ko'rinish · Hodisalar · Tekshiruvlar · Admin (faqat admin; sahifalari Bosqich 7 da).
  Har sahifa: sarlavha + bitta gap + asosiy amal; bo'sh holatlar nima chiqishini va nega bo'shligini aytadi.
  Kirish: "asosiy mazmunga o'tish" havolasi, fokus halqalari, Esc bilan yopiladigan menyu/oyna.
- **Backend** (subagent): `core/i18n.py` (160 kod × uz/ru/en, `Accept-Language` middleware), `core/errors.py` —
  javob `{"detail": <tarjima>, "code": ...}` (422 da `code: validation_error`); `app/api/*` dagi barcha `HTTPException`
  koddli xatoga o'tdi (statuslar o'zgarmadi); tekshiruv modullari natija yorliqlari so'rov tilida (mantiq o'zgarmagan,
  saqlangan natijalar tegilmagan); Telegram ogohlantirish matni admin tilida. Frontend har so'rovda `Accept-Language`
  yuboradi va `ApiError(code)` o'qiydi.
- Sahifalarni 5 ta `ui-designer` subagent parallel o'tkazdi (landing/auth, tekshiruvlar, tarix/hisobot, dashboard, Events);
  umumiy komponentlar, qobiq, i18n/tema infratuzilmasi va integratsiya — asosiy sessiyada.
- Tekshirildi: ✅ backend 223 pytest (yangi 36: Accept-Language, coded xatolar 3 tilda, katalog to'liqligi va
  placeholder'lar, tekshiruv yorliqlari ru/en); ✅ jonli: login xatosi uz/ru/en, telefon tekshiruvi ruscha yorliqlar;
  ✅ `tsc`, `NEXT_DIST_DIR=.next-build npm run build` (13 route); ✅ smoke matritsasi 72/72 (6 asosiy sahifa × light/dark ×
  uz/ru/en × desktop/360px) va dark/en'da barcha 22 sahifa; ✅ kontrast; ✅ i18n kalitlari.
  360px'dagi gorizontal skroll (landing/login yuqori paneli, dashboard to'ri) topilib tuzatildi.
- ⚠️ Tekshirilmadi / cheklov: ekran o'qigichlar bilan haqiqiy sinov; dashboard "kritik hodisalar" sarlavhalari hali asl tilda
  (statistika API Bosqich 8 da yangilanadi); admin formalaridagi Pydantic validator xatolari (api_key_env, rang, qoida)
  422 ro'yxati sifatida — matni o'zbekcha; ulagich `ConfigError` matnlari ru/en da o'zbekcha qism bilan.

### v2 — Bosqich 5: tarjima — en / ru / uz (2026-11-14)
> 2026-11-16: Google Cloud Translation o'z NLLB servisi bilan almashtirildi — pastdagi Google'ga oid qismlar (`translator.py`,
> `GOOGLE_TRANSLATE_API_KEY`, 450 000 belgi chegarasi) tarixiy. Joriy holat: "v2 dan keyin — tarjima servisi" yozuvi.
- Jadvallar (`0009_translations`): `event_translations` (hodisa × til: title, summary, provider
  `source|template|translit|google|cache|none`, status `done|pending|failed|skipped`, xato, urinishlar, keyingi urinish),
  `translation_cache` (sha256(manba til | maqsad til | matn) → tarjima), `translation_usage` (oy bo'yicha belgilar).
- `services/i18n/text.py`: til aniqlash API'siz (yozuv + o'ziga xos harflar: uz-kirill ў қ ғ ҳ, qozoq ә ұ і һ,
  tojik ҷ ӣ ӯ, qirg'iz ң ө ү; lotinda o'zbekcha so'zlar va UZCERT'ning ş/ç/ö) — `events.lang` aniqlangan tilga
  yangilanadi (asli `extra.feed_lang`); o'zbek kirill → lotin rasmiy jadval bilan (ye/ts qoidalari); apostroflar ' ga.
- `templates.py`: ransomware qurboni, CVE, breach, indikator, uzilish sarlavhalari uch tilda shablondan — Google'ga
  yuborilmaydi (faqat erkin matn — summary).
- `translator.py`: rasmiy Cloud Translation **Basic v2** (`POST …/language/translate/v2`, `q` ≤128, `format=text`,
  kalit `X-Goog-Api-Key` sarlavhasida — URL/loglarda ko'rinmaydi); xato javoblari → kalit rad etildi / limit / xato.
  `googletrans` kabi qiruvchi kutubxonalar ishlatilmadi. `FakeTranslator` — testlar uchun.
- `worker.py`: `ensure_rows` (yangi va eski hodisalar uchun reja, har tsiklda), `process_pending` — jiddiylik bo'yicha
  navbat, paketlar (≤128 satr, ≤25k belgi), kesh, sarlavha 300 / matn 600 belgigacha, oylik chegara
  `TRANSLATE_MONTHLY_CHAR_LIMIT` (450 000), 3 urinish (5→10 daq), kalit rad etilsa 1 soat pauza, 429 da Retry-After;
  o'zbekcha javob kirillda kelsa — lotinga. Manba `translate=false` bo'lsa — `skipped` (yopiq Telegram guruhlari).
- API: `GET /api/events?lang=en|ru|uz` — sarlavha/matn shu tilda, zanjir: so'ralgan → en → asl; qo'shimcha
  `original_title/summary`, `source_lang`, `display_lang`, `translated`, `translation_status`; matn qidiruvi tarjimalarda ham.
  ⚠️ Bosqich 4 dagi asl til filtri `lang` → **`source_lang`** ga o'zgardi (`lang` endi ko'rsatish tili, spetsifikatsiya bo'yicha).
  Admin: `GET /api/admin/translations` (navbat holati til bo'yicha, oy belgilari, chegara, kesh, oxirgi xatolar),
  `POST …/retry-failed`, `POST …/run`.
- Jonli (`~/osint-backups/osint-pre-phase5-*.sql`): 56 hodisa → reja: asl til nusxasi 40, shablon 11 (en), qolgani
  `pending` (kalit yo'q); aniqlangan tillar: en 19, ru 18, uz 14, kk 5.
- Tekshirildi: ✅ 187 pytest (til aniqlash 8 holat, transliteratsiya, normallashtirish, 5 shablon, reja: nusxa / translit /
  shablon / skipped; navbat: jiddiylik tartibi, kesh (2-marta provayderga bormaydi), byudjet to'xtatadi, 3 urinishdan keyin
  failed va retry, kalit rad etilganda pauza, 429; Google so'rov shakli va xato turlari (MockTransport), API: til zanjiri,
  qidiruv tarjimada, admin endpointlar).
- ⚠️ Tekshirilmadi: haqiqiy Google tarjimasi (kalit yo'q — `GOOGLE_TRANSLATE_API_KEY` kerak); `X-Goog-Api-Key` sarlavhasi
  Google tomonidan qabul qilinishi (Google API'larining umumiy qoidasi, jonli sinalmagan).

### v2 — Bosqich 4: kategoriyalar va klassifikator (2026-11-14)
- `services/events/classifier.py` — qoidalar ma'lumot sifatida (`categories.rules`: `stems` {til: [...]},
  `patterns`, `exclude`, `weight`, `min_score`); ball: sarlavhadagi stem 2, matndagi 1, pattern 3, × weight; tengda —
  jiddiyroq kategoriya. Normallashtirish: kichik harf, ё→е, apostroflar, TOPIC_NOISE, UZCERT'ning turkcha harflari
  (ş→sh, ç→ch, ö→o', ğ→g'). Tartib: manbaning qat'iy kategoriyasi → ulagich bilgani → qoidalar → `other`.
  Hodisada `extra.fixed_category` yoki `extra.classifier` {score, hits}; ulagich ko'targan jiddiylik — `extra.severity_floor`.
- `0008_category_rules` — 14 kategoriya uchun boshlang'ich qoidalar (`TOPIC_STEMS`, `TOPIC_PATTERNS`, `dedup._TOPICS`
  asosida, en/ru/uz/kk) va eski news/telegram/tg_group yozuvlarini tasniflash; ransomware/leak o'z kategoriyasida qoladi.
- API: `GET /api/categories` (hamma; nomlar en/ru/uz, rang, ikon, hodisalar soni), admin:
  `GET|POST /api/admin/categories`, `GET|PATCH|DELETE /api/admin/categories/{id}` (o'chirishda hodisalar `other` ga,
  tizim kategoriyalari faqat disable, `other` ni o'chirib bo'lmaydi; jiddiylik o'zgarsa hodisalarga qo'llanadi),
  `POST /api/admin/categories/reorder`, `POST /api/admin/categories/reclassify?dry_run=true|false` (o'tishlar soni va
  namunalar), `PATCH /api/events/{id}` (qo'lda kategoriya → `category_locked`).
- `GET /api/events` filtrlari (hammasi birlashadi, ro'yxatlar vergul yoki takror bilan): `category`, `severity`,
  `country`, `channel`, `source` (ID yoki nom), `scope` (standart `regional`; `global`, `all`), `lang`, `date_from`,
  `date_to` (Toshkent kuni), `q` (sarlavha/matn/manba/guruh; `%` va `_` ekranlanadi). v1 `category=news|telegram|tg_group`
  → kanal filtri (eski Events tablari ishlaydi).
- Jonli: 0008 qo'llandi (`~/osint-backups/osint-pre-phase4-*.sql`); qoidalar admin API orqali kuchaytirildi (hujjat
  o'g'irlash → leak/espionage), qayta tasniflash: dry-run 3 o'tish → qo'llandi. ❗ Shu qo'llashda 8 ta KEV hodisasining
  jiddiyligi `high` → `medium` ga tushdi (0008 dan oldin ulagich darajasi saqlanmagan edi) — SQL bilan tiklandi,
  0008 ga himoya qo'shildi (kategoriyadan yuqori daraja `severity_floor` ga yoziladi) va regressiya testi.
  Hozirgi taqsimot: vulnerability 18, other ~12, fraud 6, leak 8, espionage 7, law-enforcement 3, malware 2.
- Mobil: bildirishnoma nishoni 1px chetga chiqib gorizontal skroll berardi — tuzatildi.
- Tekshirildi: ✅ 164 pytest (22 ta haqiqiy sarlavha bo'yicha klassifikator, qoidalar validatsiyasi, CRUD/422/409,
  reorder, o'chirishda `other`, qayta tasniflash dry-run/apply va lock, qo'lda o'zgartirish, jiddiylik "floor", barcha
  filtrlar kombinatsiyasi, pipeline tasnifi, 0008 upgrade/downgrade); ✅ `tsc`, smoke (admin, analyst) toza.
- ⚠️ Cheklov: umumiy "xakerlar hujum qildi" xabarlari (aniq tur aytilmagan) `other` ga tushadi — 15 kategoriyada umumiy
  "hujum" yo'q; qoidalarni admin panelida (Bosqich 7) sozlash mumkin.

### v2 — Bosqich 3: manbalar (2026-11-14)
- **Telegram** (`0006_telegram_sources`): `TG_CHATS ∪ TG_LEAK_CHATS` dagi har chat — alohida manba `Telegram: <kalit>`
  (22 ta), `config.chat`, kursor `state.last_id` (faqat yangi xabarlar), leak chatlar — qat'iy kategoriya `leak`.
  `translate`: ochiq kanal (username) yoqiq, raqamli ID (yopiq chat) o'chiq. Dialoglar ro'yxati soatiga bir marta
  olinadi (har chat uchun GetDialogs chaqirilmaydi). Yagona "Telegram (akkaunt)" o'chirildi; eski TG yozuvlari
  per-chat manba o'sha xabarni qayta ko'rganda avtomatik bog'lanadi. ⚠️ Sessiya bekor qilingani sabab hammasi `auth_missing`.
- **Yangi ulagichlar** (5 ta subagent parallel yozdi, men birlashtirdim; har biri joriy hujjat bo'yicha tekshirilgan):

  | Manba (kind) | Kalit | Holat | Izoh |
  |---|---|---|---|
  | ransomware.live PRO (`ransomware_live_pro`) | `RANSOMWARE_LIVE_API_KEY` | auth_missing | `/victims/?country&year&month`, `X-API-KEY`, 60/daq; v2 zaxira sifatida yoqiq, takrorlar `dedup_key` bilan birlashadi |
  | RansomLook (`ransomlook`) | — | ✅ ok | `/api/recent/100`, davlat maydoni yo'q → sarlavhadagi domen / matn |
  | HIBP breaches (`hibp_breaches`) | — | ✅ ok (3 yangi) | `/api/v3/breaches`, HIBP RSS o'rniga (RSS o'chirildi); domen/matnga qarab regional/global |
  | CISA KEV (`cisa_kev`) | — | ✅ ok (8 yangi) | `cisagov/kev-data` (develop), ETag/304, scope global |
  | NVD critical CVEs (`nvd_cves`) | `NVD_API_KEY` (ixtiyoriy) | disabled (shovqinli) | 2.0 API, CRITICAL, ≤120 kun oyna, kalitsiz 6 s pauza |
  | URLhaus, ThreatFox (`urlhaus`, `threatfox`) | `ABUSECH_AUTH_KEY` | auth_missing | faqat .uz .kz .kg .tj .tm; defang; havola — abuse.ch hisobot sahifasi |
  | OpenPhish (`openphish`) | — | ✅ ok (0 mos) | mintaqa domeni yoki `config.brands` (aniq brendlar ro'yxati); query string saqlanmaydi; havola — urlscan.io domen sahifasi |
  | LevelBlue OTX (`otx_pulses`) | `OTX_API_KEY` | auth_missing | `pulses/subscribed`, `modified_since` kursor, TLP red/amber tashlanadi |
  | Cloudflare Radar (`cloudflare_radar`) | `CLOUDFLARE_API_TOKEN` | auth_missing | `radar/annotations/outages` davlat bo'yicha |
  | KG-CERT (`html_list`) | — | degraded (eng yangisi 2025-11) | RSS yo'q — server-rendered yangiliklar sahifasi, umumiy `html_list` ulagichi |
  | CERT.TJ (rss) | — | disabled | lentada faqat WordPress namunasi |
  | sts.kz, kz-cert.kz | — | **blocked** | Firewall CAPTCHA / 403 — chetlab o'tilmaydi; "Google News: KZ-CERT / STS" ikkilamchi manbasi |

  UZCERT — `default_countries: ["UZ"]`. cert.gov.kz — JS ilova, ochiq lenta yo'q; uning hujjatlanmagan ichki JSON
  endpoint'i ataylab ishlatilmadi. Turkmaniston — ochiq CERT sayti topilmadi (cert.gov.tm/cert.tm DNS yo'q).
- `docs/connectors.md` — ulagich yozish shartnomasi (qoidalar, `RawItem`, `extra.template`: ransomware_victim, cve,
  breach, indicator, outage). Yangi tur = bitta fayl + `connectors/__init__.py` importi.
- Pipeline: `config.default_countries` (matnda davlat topilmasa), `sector` — `geo.detect_sector()` (davlat, moliya,
  sog'liqni saqlash, telekom, ta'lim). SSRF tekshiruvidagi DNS javoblari 5 daqiqa keshlanadi.
- Testlar parallel ishlay oladi: har pytest jarayoni o'z bazasida (`<db>_test_<pid>`, oxirida o'chiriladi).
- Tekshirildi: ✅ 126 pytest (har ulagich: yozib olingan haqiqiy javob — UZCERT, Google News, ransomware.live, RansomLook,
  HIBP, KEV, NVD, OpenPhish, KG-CERT sahifasi; kalitli API'lar — hujjatdagi namuna shaklida; mintaqa filtri, kursor,
  304, 401/403, defang, query string olib tashlanishi, dedup_key mosligi; per-chat seed va downgrade; Telegram kursori);
  ✅ jonli: 0006–0007 qo'llandi (`~/osint-backups/osint-pre-phase3-*.sql`), kalitsiz yangi manbalar "hozir yig'ish" bilan:
  RansomLook, HIBP (3), KEV (8), OpenPhish, KG-CERT, Google News KZ-CERT — hammasi 200; baseline yozuvlar ogohlantirmadi.
- ⚠️ Tekshirilmadi: kalitli manbalar jonli (PRO, URLhaus, ThreatFox, OTX, Radar — kalit yo'q); OTX `targeted_countries`
  formati va tartibi; ransomware.live PRO `/victims/` qator chegarasi; Telegram per-chat jonli (sessiya bekor).

### v2 — Bosqich 2: yig'uvchi dvigatel (2026-11-14)
- `services/events/scheduler.py` — bitta 300 s tsikl o'rniga **har manba o'z jadvali**: `next_run_at = now + interval ×
  random(1 ± jitter)`; rejasiz manbalar ishga tushganda bir interval ichida tasodifiy taqsimlanadi; tsikl har 15–30 s,
  bir vaqtda ≤ 8 yig'ish. Jadval, ETag/Last-Modified va kursor holati bazada (restart qayta yuklamaydi).
  Xato → eksponensial backoff (±20%, ≤ 6 soat), 429/503 `Retry-After` va Telegram `FloodWaitError` hurmat qilinadi;
  muvaffaqiyatda avtomatik tiklanadi. PostgreSQL advisory lock — ikkinchi worker ikkinchi rejalashtiruvchini ochmaydi.
- Holatlar: `ok`, `degraded` (sekin >15 s / oxirgi 10 urinishda ≥3 xato / lentaning eng yangi elementi >14 kun —
  `config.stale_after_days`), `down` (ketma-ket ≥3 xato), `blocked` (403, 429, challenge/CAPTCHA sahifasi),
  `auth_missing` (kalit/login yo'q yoki 401), `disabled`, `never_run`. Har urinish — `source_runs` qatori (30 kun saqlanadi).
- `services/connectors/` — tur bo'yicha ulagichlar (`@register`): `rss`, `google_news`, `ransomware_live`, `telegram`
  (t.me/s), `telegram_user`. `connectors/http.py`: bir xostga bittadan so'rov + 1–4 s tasodifiy pauza, shartli so'rov
  (304 = sog'lom, yangisiz), holat kodlari → xato turlari, **SSRF** (har so'rov va redirect oldidan DNS: xususiy, loopback,
  link-local, reserved manzillar rad etiladi). User-Agent endi ochiq: `OSINT-Platform/2.0 (+repo)` (brauzerga o'xshatilmaydi) —
  52 manbadan hech biri bu sabab bloklamadi.
- `services/events/pipeline.py`: URL faqat http(s); `EVENTS_SINCE` va kategoriya `retention_days`; **baseline** — manbaning
  birinchi muvaffaqiyatli yig'ishi faqat `backfill_days` (≥ `EVENTS_SINCE`) oynasini yozadi, `is_baseline=True`, 🔔 da
  ko'rinmaydi; oynadan eski yangi elementlar yoziladi, lekin ogohlantirmaydi. Takrorlar endi tashlanmaydi:
  mavjud hodisaning `also_reported_by` ro'yxatiga qo'shiladi (yangilik imzosi + manbalararo `dedup_key`, masalan
  ransomware qurboni domeni). `services/events/filters.py` — eski `aggregator.py` dagi matn/filtr yordamchilari.
  `aggregator.py`, `collector.py` va kodidagi `FEEDS` ro'yxati olib tashlandi.
- `0005_event_uid_v2`: uid = sha256(manba nomi | URL | sarlavha) — kategoriyasiz (klassifikator o'zgartirsa ham barqaror).
- Admin API (`/api/admin/*`, faqat admin): `connectors`, `sources` (ro'yxat + filtr status/kind/enabled, 24 soatlik elementlar,
  7 kunlik uptime, kalit bormi), yaratish/tahrirlash/o'chirish (hodisalar manba nomi bilan qoladi), enable/disable,
  `test` (dry run — bazaga, ETag'ga, kursorga hech narsa yozilmaydi; saqlanmagan qoralama uchun ham), `run` (hozir),
  `runs` (tarix), `export`/`import` (JSON, nom bo'yicha upsert), `collector`. `api_key_env` — faqat `..._API_KEY/_KEY/_TOKEN`
  nomi (SECRET_KEY, DATABASE_URL, TG_* rad etiladi). `POST /api/events/refresh` — backoff'da bo'lmagan va oxirgi tekshiruvi
  intervalining yarmidan eski manbalarni yig'adi (Google News / ransomware.live ortiqcha so'ralmaydi).
- Bildirishnomalar: kategoriyalar `categories.notify` dan, baseline hodisalar hisoblanmaydi.
- `telegram_user.get_client()`: sessiya tekshiruvi xatosi endi logga turi bilan yoziladi va mijoz qayta yaratiladi
  (Telethon `is_user_authorized()` bitta vaqtinchalik xatoni jarayon umri bo'yi keshlardi).
- Tekshirildi: ✅ 74 pytest (jitter chegaralari, backoff o'sishi/cheki/Retry-After, baseline → 304 → yangi element,
  500×3 → degraded/degraded/down va tiklanish, 403/429/challenge/401, kalitsiz manba tarmoqqa chiqmaydi, SSRF (ichki DNS),
  sekin va eskirgan lenta, yangilik va ransomware takrori → also_reported_by, yozib olingan UZCERT/Google News/ransomware.live
  javoblari, advisory lock, 15 admin route × 401/403, CRUD, ichki URL'lar 422, dry run hech narsa yozmaydi, run now + tarix,
  eksport/import, FloodWait → RateLimited); ✅ jonli: 63 manba taqsimlandi, ~15 daqiqada 56 urinish — 52 `ok`, 0 `blocked`,
  15 ta takror `also_reported_by` ga tushdi; ✅ `tsc`, smoke (admin va analyst) toza.
- ❗ **Telegram sessiyasi bekor qilingan**: `AuthKeyUnregisteredError` (Telegram kalitni o'z tomonida o'chirgan — akkaunt
  sozlamalarida sessiya tugatilgan yoki Telegram o'zi chiqargan). 10:33 UTC da ishlagan, 14:20 UTC da bekor; aniq vaqt noma'lum
  (eski yig'uvchi xatoni yutib, keshdagi xabarlarni qaytarib turgan). Testlar Telegram'ga ulanmaydi (muhit tozalanadi,
  `TG_SESSION_PATH` vaqtinchalik). **Qayta login kerak**: `docker-compose exec backend python scripts/tg_login.py`.
  Manba `auth_missing`, soatiga bir qayta tekshiriladi va login'dan keyin o'zi tiklanadi.
- ⚠️ Tekshirilmadi: Telegram ulagichi jonli (sessiya yo'q); bir nechta uvicorn worker bilan advisory lock (faqat testda,
  ikki ulanish bilan); `Retry-After` HTTP-sana ko'rinishi jonli manbada.

### v2 — Bosqich 1: ma'lumot modeli (2026-11-14)
- Modellar: `models/category.py` (`Category`: slug, nom/tavsif en/ru/uz, severity, rang tokeni, Lucide ikon, notify,
  retention_days, tartib, enabled, is_system, `rules` JSONB), `models/source.py` (`Source`: kind, `config` JSONB, til,
  qat'iy kategoriya, scope, region/cyber filtr, translate, interval/jitter/backfill, `api_key_env` — faqat o'zgaruvchi NOMI,
  ETag/Last-Modified, `next_run_at`, `state` JSONB, `baseline_done`, sog'liq maydonlari; `SourceRun` — har urinish).
  `events` ga: source_id, category_id, category_locked, channel, scope, severity, countries[], sector, actor,
  matched_keywords[], extra, also_reported_by, is_baseline (+ GIN indeks countries). `events.category` — slug (48).
- Migratsiyalar: `0003_v2_data_model` (jadvallar + 15 kategoriya; notify/retention — `NOTIFY_CATEGORIES`,
  `EVENTS_RETENTION_KEEP`, `EVENTS_RETENTION_DAYS` dan bir marta), `0004_seed_sources` (v1 `FEEDS` ning **muzlatilgan nusxasi**
  — 63 manba, `interval_seconds = max(ttl, min_interval)`; eski qatorlar: `🔎 … ·` → `matched_keywords`, channel, source_id
  nom bo'yicha, countries matndan, ransomware/leak → category_id + severity). Downgrade `🔎` prefiksini qaytaradi.
- `services/events/geo.py` — `detect_countries()`; `feeds.REGION_KEYWORDS` endi `COUNTRY_KEYWORDS` (davlat bo'yicha) +
  `REGIONWIDE_KEYWORDS` dan yig'iladi (so'zlar to'plami o'zgarmadi — diff bilan tekshirildi).
- Hozirgi yig'uvchi (Bosqich 2 da almashtiriladi) yangi ustunlarni to'ldiradi; kalit so'zlar endi summary'ga yopishtirilmaydi.
  `GET /api/events` — `category` hamon slug satr, yonida yangi maydonlar. Frontend kalit so'zlarni `matched_keywords` dan oladi.
- Tekshirildi: ✅ 26 pytest (seed: 15 kategoriya / 63 manba; eski qatorlarni ko'chirish va downgrade'da tiklash — vaqtinchalik
  bazada; davlatlarni aniqlash 6 holat; API maydonlari); ✅ jonli baza: `0004_seed_sources`, 38 hodisa: prefiksli summary 0 ta,
  25/38 manbaga bog'landi, 21/38 da davlat; ✅ `tsc`, smoke toza. Bosqichdan oldingi nusxa:
  `~/osint-backups/osint-pre-phase1-20261114-153919.sql`.
- ⚠️ Cheklov: Google News orqali kelgan 13 ta eski yozuv `source_id` siz (nashr nomi qaysi GN so'rovidan kelgani noma'lum);
  17 hodisada davlat yo'q (UZCERT kabi milliy manbalar matnda davlat nomini yozmaydi — Bosqich 3 da manba bo'yicha standart davlat).

### v2 — Bosqich 0: poydevor (2026-11-14)
- Tarmoq `feat/v2-upgrade`; baza nusxasi `~/osint-backups/osint-pre-v2-20261114-145705.sql` (6 jadval, 37 hodisa).
- **Alembic**: `backend/alembic.ini`, `backend/migrations/` (async env, URL — `settings.database_url`).
  `0001_baseline` — v1 sxemasi qo'lda yozilgan; `0002_user_roles` — `users.role` (`admin`|`analyst`, CHECK) va `users.locale`.
  `scripts/migrate.py`: `alembic_version` yo'q, lekin jadvallar bor bo'lsa → avval `stamp 0001_baseline`, keyin `upgrade head`
  (eski o'rnatmalar ham avtomatik o'tadi). `create_all` `main.py` dan olib tashlandi. Dockerfile `CMD` → `scripts/start.sh`.
- **Rollar**: `ADMIN_EMAILS` (backend/.env ga egasining manzili yozildi) → admin; ro'yxat bo'sh va admin yo'q bo'lsa — eng eski faol
  foydalanuvchi; ro'yxatdan o'tgan birinchi foydalanuvchi ham admin. Hech kim avtomatik pastga tushirilmaydi.
  `require_admin` (`AdminUser`) → `POST /api/events/refresh`, `/api/telegram/*` (keyin `/api/admin/*`). `GET/PATCH /api/auth/me`
  endi `role`, `locale`. `GET /api/auth/config` → `registration_open`. Nofaol akkaunt login qila olmaydi.
- `REGISTRATION_OPEN` (bo'sh = faqat development'da ochiq). `ENVIRONMENT` development/test emas va `SECRET_KEY` standart yoki
  <32 belgi bo'lsa — backend **ishga tushmaydi**.
- `python-jose 3.3.0` (CVE-2024-33663) → **PyJWT 2.15.1**; Alembic 1.14 → 1.20.1.
- **pytest**: `backend/tests/` (pytest 9.2, pytest-asyncio 1.5, httpx `ASGITransport`), `requirements-dev.txt`, image `DEV=1`
  build argumenti bilan. `conftest.py`: barcha muhit o'zgaruvchilari tozalanadi, `OSINT_ENV_FILE` → mavjud bo'lmagan fayl
  (haqiqiy `.env` va Telegram sessiyasi testga tushmaydi), `<baza>_test` har sessiyada qayta yaratiladi va migratsiya qilinadi,
  har testdan oldin jadvallar bo'shatiladi; testda `NullPool`.
- Frontend: `Me` turiga `role`/`locale`; `/me` bir sahifada bir marta so'raladi (kesh); Sidebar va Events Telegram holatini faqat
  admin uchun so'raydi (analyst'da 403 konsol xatosi bo'lardi).
- Tekshirildi: ✅ 17 pytest (ro'yxat/login/me, 409, yopiq ro'yxat, locale, nofaol foydalanuvchi, admin route'lar 401/403/200,
  rol tayinlash ikki yo'li, SECRET_KEY bilan production ishga tushmasligi — subprocess, JWT buzilgan/muddati o'tgan,
  migratsiyalar base↔head); ✅ baseline: zaxira nusxadan tiklangan baza (stamp+upgrade) va bo'sh bazadan qurilgan sxema
  `pg_dump --schema-only` da bir xil; ✅ jonli baza: `0002_user_roles`, egasi admin, test akkaunti analyst, 37 hodisa joyida,
  yig'uvchi 67 element yig'di (Telegram ham), Telegram sessiya fayli joyida; ✅ jonli 403/200 (analyst/admin);
  ✅ `tsc`; ✅ smoke 22/22 analyst va admin tokenlari bilan.
- ⚠️ Tekshirilmadi: `REGISTRATION_OPEN` o'chiqligida frontend register sahifasining xabari (backend 403 matnini ko'rsatadi);
  Events sahifasidagi "Yangilash" tugmasi analyst uchun hali ko'rinadi (bosilsa 403 xabari) — Bosqich 7 da yashiriladi.

### 2026-11-14, 3-sessiya davomi (Bosqich 13: username moduli → faqat Telegram)
Foydalanuvchi talabi: *"username bo'yicha qidirish faqat Telegram orqali bo'lsin; ID'ni bilgan holda username qachon
o'zgartirilganini topish; qaysi guruhlarga a'zo ekanini chiqarish"*.
- **`POST /api/search/username`** endi `services/collectors/telegram_account.py` (`TelegramAccountCollector`) — foydalanuvchining
  o'z Telegram akkaunti (Telethon) orqali. Kirish: `@nom`, `nom`, `t.me/nom` yoki raqamli ID (`93372553`, `id93372553`,
  `-100…`). 13 saytli eski `collectors/username.py` repoda qoldi, lekin **ulanmagan**.
- Natija qatorlari: **Telegram akkaunt** (ID, tur: foydalanuvchi/bot/kanal/guruh, ochiq ism, belgilar: premium/tasdiqlangan/
  scam/fake/o'chirilgan) · **Username** (barcha faol usernamelar) · **Bio / Tavsif** · **Shaxsiy kanal** ·
  **Username tarixi** · **Username avvalgi egasi** · **Guruh: …** (har bir umumiy guruh: ochiq/yopiq, a'zolar soni, shu akkaunt
  yozgan xabarlar soni va birinchi/oxirgi sanasi — dastlabki 15 guruh uchun).
- **Username tarixi** — Telegram o'tgan o'zgarishlarni **bermaydi**. Yangi jadval `tg_observations` (`models/telegram.py`): har
  qidiruvda ID + usernamelar holati yoziladi; o'zgarmagan bo'lsa `last_seen` yangilanadi, o'zgargan bo'lsa yangi qator.
  O'zgarish vaqti = ikki kuzatuv oralig'i ("@eski → @yangi: 12 noy va 14 noy oralig'ida"). Shuning uchun tarix **faqat birinchi
  qidiruvdan boshlab** va qidiruvlar orasidagi aniqlikda. ID bo'yicha qidiruv username o'zgargan bo'lsa ham akkauntni topadi
  (sessiya keshidagi access_hash orqali) — o'zgarishni aynan shu aniqlaydi. Jurnalda ism/telefon/bio **saqlanmaydi**.
- **Guruhlar** — faqat `messages.GetCommonChats`: sizning akkauntingiz ham a'zo bo'lgan guruhlar. Boshqa odamning barcha guruhlari
  ro'yxatini Telegram hech kimga bermaydi.
- **Ataylab qilinmadi** (foydalanuvchi "unsensured versiya" so'ragan): sizib chiqqan bazalar va odamlarni ommaviy kuzatib yig'ilgan
  uchinchi tomon bazalari/botlari ulanmadi ("faqat ochiq manbalar" qoidasi); telefon raqami va "oxirgi marta ko'rilgan" o'qilmaydi.
  "Margaret" → Maigret deb tushunildi; u Telegram uchun faqat `t.me/<nom>` borligini tekshiradi, shuning uchun ishlatilmadi.
- ID cheklovi: Telegram ID bo'yicha faqat akkaunt avval "ko'rgan" obyektni ochadi (umumiy guruhda uchragan yoki username bilan
  qidirilgan). Noma'lum ID → "Noaniq" qatori va tushuntirish.
- UI: `/dashboard/username` sarlavha/tavsif/namunalar, `lib/modules.ts`, landing kartasi. Natijalar to'ri mobil ekranda
  gorizontal skroll berardi (uzun bio) → `grid-cols-1` (`SearchModule.tsx`); bio endi karta matnida.
- Tekshirildi: ✅ jonli API — bot (`botfather`), kanal (`t.me/telegram`), ID (uch xil yozuvda), bo'sh username, yaroqsiz kirish
  (422), noma'lum ID; ✅ umumiy guruhlar va xabar sanoqlari (guruh moderator botlari bilan: 15 / 2 / 5 guruh, 0.9–4.2 s);
  ✅ username o'zgarishi, avvalgi egasi, "username boshqa akkauntda" — jurnalga sun'iy yozuvlar bilan (keyin jurnal tozalandi);
  ✅ `tsc`, smoke 22/22, brauzerda qidiruv → natija (desktop + mobil 360px).
- ⚠️ Tekshirilmadi: haqiqiy username o'zgarishi (faqat sun'iy yozuv bilan); oddiy foydalanuvchi akkaunti (faqat bot va kanalda
  sinaldi — umumiy guruhlar yo'li bir xil); Telegram flood-wait holati (kodi bor, yuzaga kelmadi); 100 dan ko'p umumiy guruh.
- Keyingi qadam (foydalanuvchi qarori kerak): **kuzatuv ro'yxati** — qidirilgan ID'larni fon yig'uvchi kuniga bir marta qayta
  tekshirsa, username o'zgarish vaqti bir kun aniqligida chiqadi. Hozir faqat qo'lda qidirilganda yoziladi.

### 2026-11-14, 3-sessiya (lenta sayqali: takror voqealar va shovqin)
Oldingi sessiyada qayd etilgan ikki kamchilik yopildi (kod: `events/dedup.py`, `feeds.FOREIGN_MARKERS`):
- **Takror voqealar** — yangi modul `services/events/dedup.py`: sarlavha "imzo"ga aylanadi — muhim so'zlar til va sinonimdan
  qat'i nazar tushunchaga keltiriladi (`хакеры`/`hackers`/`взломали` → `#HACK`, `Таджикистана`/`Tajik` → `#TJ`,
  `украли`/`похитили`/`steal` → `#STEAL`, `ИИ`/`AI` → `#AI` ...), qolganlari 5 harfli o'zak, bog'lovchilar tashlanadi.
  Bitta voqea = barcha tokenlar bo'yicha Jaccard ≥ 0.5 **yoki** ≥ 4 umumiy tushuncha va tushunchalar Jaccard ≥ 0.5
  (ruscha ↔ inglizcha sarlavhalar ham birlashadi). **Veto:** ikkalasida davlat bor, umumiysi yo'q (UZ ≠ KZ); ikkalasida soha bor,
  umumiysi yo'q (bank ≠ klinika) — avvalgi qoida bularni birlashtirib yuborardi. Oyna (3 kun) va tartib (to'g'ridan-to'g'ri manba,
  keyin eng eski) o'zgarmadi. Sozlash: `dedup.py` dagi `_TOPICS`/`_SECTORS`/`_COUNTRIES`, `*_THRESHOLD`.
- **Bazadagi eski takrorlar** — `backend/scripts/dedup_events.py` (`docker-compose exec backend python scripts/dedup_events.py`
  — faqat ko'rsatadi; `--apply` — o'chiradi). Ishlatildi: 40 yangilikdan **12 tasi o'chirildi** (Tojikiston hujjatlari voqeasi
  13 → 2, Turla/KZ pochta 2 → 1, Zamin.uz EN/RU 2 → 1). Oldingi holat nusxasi (46 qator):
  `~/osint-events-backup-2026-11-14-dedup.sql` (repodan tashqarida).
- **Shovqin** — `FOREIGN_MARKERS` ga jahon miqyosidagi shaxs/kompaniyalar qo'shildi (Дуров, Binance, Bybit, Coinbase, Маск,
  OpenAI, Трамп): mahalliy sayt bosgan jahon yangiligi, mintaqa so'zi bo'lmasa tashlanadi. `telegram`/`google`/`apple` ataylab
  qo'shilmadi (mahalliy firibgarlik va zaiflik xabarlarida uchraydi). Bazadagi 2 ta shunday yozuv (Дуров, Binance) o'chirildi.
  "Russian hackers breach Romania emails" (CyberNews) **qoldirildi** — bu Turla voqeasi, Qozog'iston davlat pochtasi ham nishon.
- Hozir bazada: 26 yangilik + 6 Telegram. Restartdan keyingi yig'ish: 62 element, **0 yangi** (o'chirilgan takror va shovqin qaytmadi).
- Tekshirildi: ✅ haqiqiy 40 sarlavhada quruq yurgizish (noto'g'ri birlashgan juftlik yo'q); ✅ 12 ta juftlik testi (bank/klinika,
  UZ/KZ, UZCERT zaiflik e'lonlari birlashmaydi; RU↔EN bir voqea birlashadi); ✅ shovqin filtri 9 ta holat; ✅ yig'uvchi xatosiz.
- ⚠️ Tekshirilmadi / cheklov: yangi voqea kelgandagi jonli yo'l (bu tsiklda yangi yozuv bo'lmadi); bir davlatda 3 kun ichida
  deyarli bir xil yozilgan ikki XIL voqea (soha so'zisiz) hamon birlashishi mumkin; butunlay boshqacha yozilgan nusxalar qoladi
  (Forbes Kazakhstan — 3 ta, Tojikiston — 2 ta); Telegram postlari yangiliklar bilan solishtirilmaydi; o'chirilgan takrorlar
  soni saqlanmaydi ("N ta manba yozdi" ko'rsatkichi yo'q — kerak bo'lsa `events` ga ustun qo'shish kerak).
- Eslatma: sessiya boshida backend konteyneri o'chiq edi (`Exit 255`, kompyuter qayta yoqilgan) → `docker-compose start backend`.

### 2026-11-14, 2-sessiya davomi-3 (`EVENTS_SINCE` → 2026-11-10)
- Foydalanuvchi: "11.10.2026 dan boshlab yig'sin" → **10-noyabr** deb tushunildi (assistent taklif qilgan `2026-11-10` ga javob edi;
  agar 11-oktabr nazarda tutilgan bo'lsa — `backend/.env` da `EVENTS_SINCE=2026-10-11` + `docker-compose restart backend`).
- `backend/.env`: `EVENTS_SINCE=2026-11-10`, backend restart → birinchi yig'ishda **46 ta hodisa** (40 yangilik, 6 Telegram), xatosiz.
  Yangi filtr + Google News + takror kesish yo'li endi haqiqiy ma'lumotda oxirigacha ishladi (manba → baza → Events sahifasi);
  smoke: dashboard va events (desktop + mobil) toza.
- Lentada sezilgan shovqin (filtrni sozlash uchun namunalar): "Павел Дуров предложил ... взломать его аккаунт" (Kursiv),
  "Binance возместила ... при взломе" (Turkmenportal), "Russian hackers breach Romania emails" (CyberNews — Qozog'iston faqat matn ichida).
  Tojikiston hujjatlari voqeasi turlicha sarlavhalar bilan ~12 marta qolgan (takror kesish faqat o'xshash sarlavhalarni birlashtiradi).

### 2026-11-14, 2-sessiya davomi-2 (bloklangan saytlar uchun ikkilamchi manbalar)
Foydalanuvchi so'radi: Cloudflare/403 beradigan saytlardan (BleepingComputer, CyberNews, Cyber Express, camonitor.kz, turkmenportal,
breached/cracked/darkforums) qanday ma'lumot olish mumkin → saytning o'ziga kirmasdan, ochiq ikkilamchi manbalar orqali:
- **Yangi feed turi `google_news`** (`aggregator._fetch_google_news`): `Feed.url` = Google News qidiruv so'rovi. Faqat sarlavha, nashr
  nomi, sana va Google havolasi olinadi; manba nomi `"<Nashr> (Google News)"`. Google to'liq matn bo'yicha qidiradi → mintaqa sharti
  so'rovning o'zida. 6 ta feed: BleepingComputer, CyberNews, The Cyber Express (`site:` + 5 davlat, filtrsiz), Turkmenportal
  (`site:` + kiber so'zlar + `cyber_filter`), umumiy **Google News (EN)** va **(RU)** (5 davlat × kiber so'zlar + `cyber_filter`;
  Reuters, The Record va boshqa istalgan nashr). `Feed.min_interval=1800` — fon yig'uvchi ham 30 daqiqada bir martadan ko'p so'ramaydi.
- **Leak kuzatuvchilar** (forumlarning o'zi emas, faqat xulosa/metadata; kategoriya `leak` → 🔔): Dark Web Informer RSS,
  Have I Been Pwned RSS — `region_filter` bilan.
- **Takror yangiliklar** (`collector.drop_similar`; qoida keyin kuchaytirildi — yuqorida "3-sessiya"): `news` kategoriyasida sarlavhalar so'z to'plami (4+ harfli so'zlarning birinchi
  5 harfi) bo'yicha solishtiriladi — Jaccard ≥ 0.5 va sanalar farqi ≤ 3 kun bo'lsa takror; bazadagi so'nggi 14 kunlik sarlavhalar bilan
  ham. To'g'ridan-to'g'ri manba Google nusxasidan, eski sana yangisidan ustun. Sinovda 44 → 26.
  ⚠️ Cheklov: deyarli bir xil sarlavhali ikki XIL voqea (masalan "xakerlar bank saytini buzdi" / "...vazirlik saytini buzdi", 3 kun ichida)
  bittaga birlashib ketishi mumkin; turlicha yozilgan bir voqea esa alohida qoladi.
- RSS sanalari endi `calendar.timegm` bilan (avval `mktime` — faqat konteyner UTC bo'lgani uchun to'g'ri chiqardi).
- Ishlamadi / qo'shilmadi: camonitor.kz (Google News indeksida yo'q), DailyDarkWeb RSS (ulanmadi), Mastodon @BleepinComputer (404),
  CISA (AQShga qaratilgan — kerak emas). breached.st / cracked.st / darkforums.as ga to'g'ridan-to'g'ri murojaat qilinmaydi.
- Tekshirildi: ✅ jonli sinov — Google News (EN) 18 → 17, (RU) 27 → 24 filtrdan o'tdi (Tojikiston hujjatlari o'g'irlanishi, Forbes Kazakhstan'ga
  hujum, O'zbekiston o'rmon xo'jaligi tizimiga hujum...), hammasi 10–13-noyabr → `EVENTS_SINCE` sabab lentaga tushmadi;
  ✅ takror kesish birlik testlari; ✅ yig'uvchining yozish yo'li sun'iy yozuvlar bilan (Google nusxasi va eski sana tashlanadi,
  bazadagi o'xshash sarlavha qayta yozilmaydi), sinov yozuvlari o'chirildi; ✅ restartdan keyin yig'uvchi xatosiz.
- ⚠️ Tekshirilmadi: Google News havolasining brauzerda asl maqolaga yo'naltirishi; Google'ning tez-tez so'rovda cheklashi
  (30 daq oraliq qo'yilgan); haqiqiy bugungi yozuvning UI'da ko'rinishi.

### 2026-11-14, 2-sessiya (Bosqich 11: hisobot eksporti + Events retention)
- **Hisobot eksporti** — tarix sahifasidagi har qatorda va qidiruv natijasi kartasida `JSON` / `PDF` tugmalari
  (`components/ExportButtons.tsx`):
  - API: `GET /api/search/jobs/{id}/export` → `JobReport` (`report` meta, `job`, `summary` {checked/found/not_found/error},
    `results` — holat bo'yicha saralangan). `Content-Disposition: attachment`. Faqat o'z yozuvi (begona/yo'q → 404, tokensiz → 401).
  - JSON: `lib/report.ts` `downloadReportJson()` — fayl nomi `osint-hisobot-<modul>-<so'rov>-<id>.json`.
  - PDF: alohida sahifa **`/report/[id]`** (dashboard qobig'idan tashqarida, oq "qog'oz" varaq) → «Chop etish / PDF» tugmasi
    `window.print()`; brauzerda «PDF sifatida saqlash». `globals.css` da `@media print` + `@page A4`; asboblar paneli va Aurora
    foni chop etishda yashiriladi; `document.title` = fayl nomi (PDF shu nom bilan saqlanadi).
    PDF kutubxonasi (jsPDF/reportlab) ataylab ishlatilmadi: qo'shimcha paket yo'q, kirill/o'zbek harflari muammosiz.
  - Tor ekranda hisobot jadvalida "Holat" ustuni yashirinib, nishon manba nomi ostiga tushadi.
- **Events retention** — `EVENTS_RETENTION_DAYS=90` (0 = o'chiq), `EVENTS_RETENTION_KEEP=ransomware,leak`:
  - har yig'ishdan keyin `coalesce(published, first_seen)` muddatdan eski hodisalar o'chiriladi; `KEEP` dagi kategoriyalar
    **hech qachon o'chirilmaydi** (ransomware yozuvlari 2023 yildan beri — tarixiy qiymati bor);
  - muddati o'tgan element bazaga umuman yozilmaydi (`is_expired`) — aks holda manba uni qaytargan sari har tsiklda
    "yangi" bo'lib qayta paydo bo'lardi;
  - `GET /api/events/status` ga `retention_days`, `retention_keep`, `last_purged`, `purged_total` qo'shildi; Events holat
    panelida "saqlash 90 kun" (tooltip'da tafsilot).
  - ⚠️ `.env` da bu kalitlar yo'q bo'lsa default (90 kun) ishlaydi. Hozir bazada 90 kundan eski news/telegram yo'q — hech narsa o'chmadi.
- **Events sahifalash** allaqachon bor edi ("Ko'proq yuklash", `offset`) — ro'yxatdan olib tashlandi.
- Smoke-test endi `/report/<oxirgi qidiruv>` ni ham tekshiradi (`API=` muhit o'zgaruvchisi, default `http://localhost:8000`).
- Tekshirildi: ✅ `tsc --noEmit`; ✅ `NEXT_DIST_DIR=.next-build npm run build` (13 route); ✅ smoke 22/22;
  ✅ eksport API (200 / 401 / 404); ✅ brauzerda JSON yuklanishi (tarix va qidiruv natijasidan), `/report` desktop + mobil 360px,
  headless Chrome `printToPDF` bilan A4 PDF (domen va username hisobotlari), xato holatlari (yo'q id, noto'g'ri id);
  ✅ retention: sun'iy 2025-yilgi news yozuvi o'chdi, 80 kunlik yozuv va 2023-yilgi ransomware qoldi, mantiq testi (naive sana, 0 = o'chiq).
- ⚠️ Tekshirilmadi: haqiqiy printerda chop etish va Firefox/Safari'ning print ko'rinishi (faqat Chrome); ko'p sahifali
  (50+ qatorli) hisobotning sahifa bo'linishi.

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

### Keyingi qadamlar (v2 dan keyin)
1. **Telegram'ga qayta login** (sessiya Telegram tomonidan bekor qilingan): `docker-compose exec backend python scripts/tg_login.py`
   — 22 ta Telegram manbasi `auth_missing` holatidan o'zi chiqadi.
2. Kalitlarni olish va `backend/.env` ga qo'yish: `RANSOMWARE_LIVE_API_KEY`, `ABUSECH_AUTH_KEY`,
   `OTX_API_KEY` (ixtiyoriy: `NVD_API_KEY`, `CLOUDFLARE_API_TOKEN`); backend konteynerini qayta yaratish; admin panelda manbani yoqish.
3. v2 ni `main` bilan solishtirib, qaror qilinsa merge (egasi qiladi).
4. ✅ (2026-11-16) `X-Forwarded-For` (`TRUSTED_PROXIES`), tarix hisoblagichi, Events `range` (soat aniqligida).
   Qolgan ixtiyoriy: Next 15 ga ko'chish (alohida ish; 2 ta npm audit ogohlantirishi shu bilan yopiladi).

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

- [x] **Hisobot eksporti (JSON / PDF) + Events retention (Bosqich 11, 2026-11-14)** — tafsilotlar yuqorida ("2-sessiya")

- [x] **Events: Markaziy Osiyo + kiber/leak filtri, `EVENTS_SINCE` (Bosqich 12, 2026-11-14)** — tafsilotlar yuqorida ("2-sessiya davomi", "3-sessiya")

- [x] **Username moduli → faqat Telegram (Bosqich 13, 2026-11-14)** — tafsilotlar yuqorida ("3-sessiya davomi")

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
