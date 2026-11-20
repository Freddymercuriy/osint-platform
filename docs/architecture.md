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

Fon yig'uvchining `.onion` manbalari (`onion_feed`) faqat compose ichidagi `tor` konteyneri (SOCKS5, `socks5h://tor:9050`)
orqali boradi; Tor mijozi faqat `.onion` xostlarga so'rov yuboradi, oddiy mijoz `.onion` ni DNS'ga ham so'ramaydi.

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
  Kutish ko'rinishi: `last_outcome` (oxirgi urinish: `blocked` / `rate_limited` / `error` ...), `retry_after_seconds`
  (sayt so'ragan kutish — Retry-After / FloodWait); `source_runs` da ham `retry_after_seconds` va `wait_seconds`
  (keyingi urinishgacha rejalashtirilgan). Admin → Manbalar "Holat" ustuni: sabab + HTTP, sayt so'ragan kutish,
  qayta urinishgacha jonli hisob (`WaitInfo`); muddat o'tsa satr qayta o'qiladi.
- **`services/events/scheduler.py`** — rejalashtiruvchi: `next_run_at = now + interval × random(1 ± jitter)`, xatoda
  eksponensial backoff (sayt ishlamasa — timeout / DNS / 5xx — ≤ 1 soat, blok / limit — ≤ 6 soat, intervaldan
  tez emas; Retry-After / FloodWait), PostgreSQL advisory lock bilan yagona nusxa.
- **`services/connectors/`** — ulagichlar, tur bo'yicha ro'yxatga olinadi (`@register`); yozish qoidalari:
  [`docs/connectors.md`](connectors.md). `http.py` — xost navbati va pauzalar, shartli so'rov, holat kodlari, SSRF.
- **`services/events/pipeline.py`** — bazaga yozish: http(s) havolalar, `EVENTS_SINCE` va kategoriya muddati, baseline
  (birinchi yig'ish ogohlantirmaydi), takrorlar mavjud hodisaning `also_reported_by` ga qo'shiladi. Global manbaning
  (xalqaro kiber-saytlar — 0014, NewsNow) Markaziy Osiyo belgisi bor elementi `regional` bo'ladi (`filters.region_hits`).
  Kelajak sanasi (`published > now`) yig'ish vaqti bilan cheklanadi, asl sana — `extra.published_original` (0015).
- Events eksporti: `GET /api/events/export?format=csv|json` — `/api/events` bilan bir xil filtrlar va `lang`,
  eng yangi `export.MAX_ROWS` (5000); CSV — UTF-8 BOM, formula injection himoyasi (`=`,`+`,`-`,`@` → `'`),
  sarlavhalar `X-Export-Total` / `X-Export-Count` (CORS `expose_headers`). Rate limit: `refresh_rate × 2`.
- Events holat qatori (`/api/events/status`): `failing` — yoqilgan down/blocked manbalar (nom, sabab, keyingi urinish);
  yig'uvchining o'zi bilan aralashtirilmaydi. HTTP xatolari: `http.http_error_text` (5xx, Cloudflare 52x izohi).
- Telegram: har kuzatiladigan chat — alohida `telegram_user` manbasi (`{"chat": username yoki -100id}`); dialoglar
  asosiy ro'yxat (`TG_DIALOG_LIMIT`) va "Arxiv" papkasidan (folder 1, `TG_ARCHIVE_LIMIT`) o'qiladi.
  Shu chegaradan tashqaridagi chat (ro'yxat oxirgi xabar sanasi bo'yicha — kam yoziladigan kanal pastda) username / ID
  bo'yicha to'g'ridan-to'g'ri aniqlanadi (`_resolve_joined_chat`), faqat akkaunt a'zo bo'lsa.
  Admin chat tanlash (`GET /api/telegram/chats`) — butun ro'yxat (`list_chats(full=True)`, 5 daq. kesh,
  `?refresh=true` — rate limit bilan), har chatda `monitored` (manbasi bor — `telegram_archive.is_monitored`).
  Filtr (0016 dan, barcha Telegram manbalari `scope=global` + `cyber_filter`): Markaziy Osiyo kalit so'zi
  (`TG_UZ_FILTER`, `TG_EXTRA_KEYWORDS`) topilgan xabar `regional` (mavzusiz ham o'tadi), qolgani — kiber mavzusi bo'lsa
  `global`. Regional Telegram manbasida — avvalgidek faqat kalit so'z.
- `filters.apply_filters` global manbada: "chet el" qoidasi qo'llanmaydi (u mahalliy saytlar uchun); `cyber_filter`
  mavzusiz elementni mintaqaga oid bo'lsa (`item.scope == regional` yoki mintaqa so'zi) o'tkazadi.
- `RawItem.ignore_source_category` — manbaning qat'iy kategoriyasi (`sources.category_id`) shu elementga qo'llanmaydi,
  klassifikator hal qiladi (`extra.category_free`; `reclassify` ham). Telegram: "leak" chatining global suhbati.
  `TG_MONITOR_ARCHIVED=true` — `services/events/telegram_archive.py` arxivdagi har kanal/guruh uchun manba yaratadi
  (housekeeping'da, soatiga bir; mavjud yoki o'chirib qo'yilgan manbaga tegmaydi; `state.origin = "archive"`).
- NewsNow: `connectors/newsnow.py` — mavzu sahifasi (`config.url`, faqat newsnow.com / newsnow.co.uk, so'rov
  qatorisiz, robots.txt'dagi yopiq yo'llar taqiqlangan) → `article.article-card`: sarlavha, nashr ("<nashr> (NewsNow)"),
  `data-timestamp`, havola `c.newsnow.com/A/<id>` (platforma unga kirmaydi). Takror kaliti — `newsnow:<id>`
  (havoladagi `?...` qo'shimchasi o'zgaradi). Kartochka topilmasa — xato (jim `ok` emas). Manba (0012) o'chiq qo'shiladi.
- Kalit so'zlar va regexlar kodda: `services/events/feeds.py` (hudud, mavzu, chet el belgilari), `dedup.py`, `geo.py`.
- Kategoriyalar: `categories` (15 ta, en/ru/uz, jiddiylik, rang, ikon, notify, saqlash muddati, `rules`) —
  `services/events/classifier.py` (manba → ulagich → qoidalar → `other`), `categories.py` (qayta tasniflash).
  Qoidalar bazada (admin tahrirlaydi); migratsiya ularni ustidan yozmaydi — faqat yo'q band qo'shadi (masalan
  `0017`: leak — yolg'iz "breach", yozuvlar soni / hajm, dark web / forum).
- Ustuvorlik (rahbariyat kanali): `events.priority` / `priority_band` / `priority_reasons` —
  `services/publisher/priority.py::compute` (sof funksiya: kategoriya jiddiyligi, davlat, soha, kuzatuv ro'yxati,
  manba ishonchliligi `sources.reliability`, manbalar soni, yozuvlar soni, eskirganlik, yolg'iz yashirin manba;
  global + kuzatuvsiz → low). Og'irliklar — `publisher_settings` (admin). Qayta hisoblash — `publisher/scoring.py`
  (yig'ish, birlashish, tarjima, kategoriya, kuzatuv / og'irlik o'zgarishi — 14 kun, housekeeping — bali yo'qlar).
- Rahbariyat kanali (nashr): `channel_destinations` (chat, til, rejim dry_run → review → auto, qamrov, jadval, sokin
  soatlar, chegara, sog'liq), `channel_posts` (outbox + audit, `(destination_id, dedup_key)` noyob), `bot_chats`,
  `reviewers`, `publisher_state` (offset, pauza, tekshiruv chati, bot holati) — `models/publisher.py`.
- Tarjima: `event_translations` (en/ru/uz), `services/i18n/` — til aniqlash, o'zbek kirill→lotin, shablon sarlavhalar,
  navbat (`worker.py`: kesh, oylik chegara — 0 = chegarasiz, qayta urinish; 422 / noma'lum til — darhol `failed`).
  Provayder — o'z NLLB servisimiz (`translator.py`, `TRANSLATE_API_URL`, kalitsiz): ISO kod → FLORES-200
  (`uz→uzn_Latn`, `ru→rus_Cyrl`, `en→eng_Latn`, `kk→kaz_Cyrl`, `ky→kir_Cyrl`, `tg→tgk_Cyrl`, `tk→tuk_Latn`; NLLB
  kodlarining o'zi ham qabul qilinadi). Servisda `uzn_Cyrl` yo'q — o'zbek kirill (`uz-Cyrl` / `uzn_Cyrl`) uchun model
  `uzn_Latn` bilan ishlaydi, yozuv latin.jaybi.uz dvigateli bilan almashtiriladi (`i18n/vendor/uztranslit.py` — MIT,
  o'zgartirilmagan, `text.uz_to_cyrillic` / `uz_to_latin`): manba kirill → avval lotinga, maqsad kirill → tarjimadan
  keyin kirillga; o'zbek ↔ o'zbek — servissiz. `/translate/batch` ≤ 64 matn; `max_input_length`
  (`GET /model`) dan uzun matn gaplar bo'yicha bo'linadi. Ulanish xatosi / 5xx — 2 marta qayta urinish, timeout va 422 —
  yo'q. Navbatda xato → qator `pending` (asl matn tarjima sifatida saqlanmaydi); navbatdan tashqari chaqiruvlar uchun
  `translate_or_original()` (ogohlantirish + asl matn). Mijoz ulagichlardan alohida: SSRF filtri va pauzasiz
  (URL operator sozlamasi).
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
  `next-intl` (uz/uz-Cyrl/ru/en, cookie `NEXT_LOCALE` + `users.locale`, `messages/*.json`; `uz-Cyrl.json` —
  `backend/scripts/gen_uz_cyrl_messages.py` bilan `uz.json` dan), `lib/format.ts`.
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
