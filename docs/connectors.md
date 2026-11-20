# Ulagich (connector) yozish qo'llanmasi

Manbalar bazada (`sources` jadvali). Har manba turi (`sources.kind`) — bitta ulagich klassi, bitta fayl:
`backend/app/services/connectors/<kind>.py`. Rejalashtiruvchi (`services/events/scheduler.py`) uni o'z jadvali
bo'yicha chaqiradi, natijani `services/events/pipeline.py` bazaga yozadi.

## Qoidalar (o'zgarmas)

- Faqat ochiq sahifalar, lentalar va **rasmiy API'lar**. Login devori, CAPTCHA yoki Cloudflare challenge chiqsa —
  chetlab o'tilmaydi (`SourceBlocked`). CAPTCHA yechuvchi, brauzer niqobi, proxy aylantirish, avtomatik login — yo'q.
- Faqat **metadata**: kim, nima, qachon, qaysi guruh, havola. Sizib chiqqan fayl, parol/credential, shaxsiy ma'lumot
  yuklanmaydi va saqlanmaydi. Login talab qiladigan forumlar o'qilmaydi.
- `.onion` — **faqat `onion_feed` ulagichi** (egasi qarori, 2026-11-20): faqat admin qo'shgan manbalar (ro'yxat —
  `sources` jadvali), faqat Tor orqali (`ctx.tor`, `TOR_PROXY_URL`, docker-compose `tor` xizmati), faqat v3 manzil
  va faqat mehmonga ochiq RSS / Atom lentalari. Olinadi: mavzu sarlavhasi, havola, vaqt, bo'lim, muallif taxallusi.
  Olinmaydi: post matni, fayllar, rasmlar, mavzu sahifalari; Doxes kabi xususiy shaxslar bo'limlari qo'shilmaydi.
  Tor mijozi faqat `.onion` xostlarga (redirect ham), oddiy mijoz `.onion` ni DNS'ga ham so'ramaydi.
- `.onion` saytda bloklanmaslik — **xushmuomalalik, niqoblanish emas** (`onion_feed`): har lenta o'z hajmiga mos
  tezlikda (`every_minutes`), kichik sahifa (`limit` ≤ 30), kunlik qat'iy limit (`max_requests_per_day`, 80),
  so'rovlar ketma-ket va orasida 10–30 s, "Sinash" — faqat 1 lenta, 403 / 429 / challenge / login — darhol to'xtash.
  Yo'q: brauzer niqobi, Tor zanjirini ataylab almashtirish, CAPTCHA yechish, akkaunt / login.
- Kalit faqat muhitda (`backend/.env`), bazada — o'zgaruvchi NOMI (`sources.api_key_env`). Kalit logga, xatoga,
  `extra` ga yozilmaydi.
- Ishlatishdan oldin API'ning **joriy hujjatini** oching: endpoint, autentifikatsiya, limitlar, javob shakli.

## Shartnoma

```python
from app.services.connectors.base import (
    AuthMissing, ConfigError, Connector, ConnectorError, FetchContext, FetchResult, RateLimited, RawItem,
    SourceBlocked, register,
)

@register
class MyConnector(Connector):
    kind = "my_kind"                 # sources.kind
    title = "Odam o'qiydigan nom"
    key = None | "required" | "optional"
    default_key_env = "MY_API_KEY"   # key bo'lsa; backend/.env.example ga ham qo'shing
    config_fields = ("url",)         # config JSON'dagi asosiy maydonlar (admin formasi)

    def validate_config(self, config: dict) -> None: ...      # noto'g'ri bo'lsa ConfigError
    def target_urls(self, source) -> list[str]: ...            # admin kiritgan URL'lar (SSRF tekshiruvi uchun)

    async def fetch(self, ctx: FetchContext) -> FetchResult:
        resp = await ctx.http.get(url, headers={...}, params={...})   # xato kodlari avtomatik xatoga aylanadi
        ...
        return FetchResult(items, resp.status_code, state={...} | None)
```

- `ctx.source` (`SourceView`): `name, kind, config, lang, scope, region_filter, cyber_filter, etag, last_modified,
  state, backfill_days, category_slug`. `ctx.api_key` — kalit qiymati (bo'lsa). `ctx.dry_run` — admin "sinash"
  tugmasi: hech narsa saqlanmaydi; shartli so'rov yubormang, kursorni ishlatmang.
- `ctx.http.get/post(url, *, headers, params, json, etag, last_modified, allow_not_modified, expect_html)` —
  bir xostga bittadan so'rov + pauza, SSRF tekshiruvi; 401 → `AuthMissing`, 403/challenge → `SourceBlocked`,
  429/503+Retry-After → `RateLimited`, boshqa ≥400 → `ConnectorError`. Ulagich o'zi `httpx` mijozi ochmaydi.
- `ctx.tor` — Tor mijozi (xuddi `ctx.http` interfeysi), faqat `uses_tor = True` ulagichlarga; `TOR_PROXY_URL`
  bo'lmasa manba `auth_missing`. `slow_ms` — "sekin" (degraded) chegarasi, standart 15 s (Tor manbasi — 180 s).
- `FetchResult.state` — kursor (masalan oxirgi ko'rilgan ID/sana); `None` — o'zgarmaydi. Keyingi chaqiruvda
  `ctx.source.state` da keladi. Birinchi chaqiruvda (`state` bo'sh) `backfill_days` oynasini oling.
- `RawItem` maydonlari: `title`, `url` (faqat http/https — boshqasi tashlanadi), `summary` (qisqa, ≤ 600 belgi),
  `published` (UTC, tz-aware), `lang`, `source_name` (ko'rsatiladigan manba nomi, odatda bo'sh), `category`
  (slug — aniq bilsangiz: `ransomware`, `leak`, `vulnerability`, `malware`, `phishing`, `ddos-outage`, `advisory` ...),
  `channel` (`api` — API manbalar uchun), `scope` (`regional` | `global`), `severity` (`info`…`critical`, kategoriyadan
  yuqori bo'lsa), `countries` (ISO-2: UZ KZ KG TJ TM), `sector`, `actor` (ransomware guruhi), `extra` (pastda),
  `dedup_key` (manbalararo bir xil obyekt).
- `countries`/`sector` bo'sh bo'lsa pipeline matndan aniqlaydi (`services/events/geo.py`).
- Mintaqa: Markaziy Osiyo — 5 davlat. Davlat maydoni bo'lmagan global lentalar (KEV, NVD) `scope="global"`.

### `extra` — tuzilgan maydonlar va shablonlar

Sarlavhasi tuzilgan ma'lumotdan yasaladigan elementlar mashina tarjimasiga yuborilmaydi — UI/backend ularni
lokal shablon bilan uch tilda quradi. Ulagich inglizcha `title` ham beradi (zaxira):

| `extra.template` | Majburiy maydonlar |
|---|---|
| `ransomware_victim` | `victim`, `group`, `domain`, `activity` (+ `dedup_key = victim_key(victim, domain)` — `connectors/ransomware_live.py`) |
| `cve` | `cve_id`, `vendor`, `product`, `cvss` (bo'lsa), `kev` (bool), `due_date` (KEV) |
| `breach` | `breach_name`, `domain`, `pwn_count`, `data_classes` (toifalar nomi, qiymatlar emas), `breach_date` |
| `indicator` | `ioc_type` (`url` / `domain` / `ip`), `ioc` (defang: `hxxp`, `[.]`), `host`, `threat` (oila/teg) |
| `outage` | `country`, `scope`, `cause`, `start`, `end` |

## Test

- `backend/tests/test_connector_<kind>.py`; tarmoqsiz: `tests/helpers.use_transport(monkeypatch, handler)`.
- Yozib olingan haqiqiy javob — `backend/tests/fixtures/<kind>_*.json|xml` (kalitsiz ochiq API bo'lsa yozib oling,
  kichraytiring; kalitli API — hujjatdagi namuna javob shaklida, faylning boshida/README'da manbasini yozing).
- Ishga tushirish: `docker-compose exec -T backend pytest tests/test_connector_<kind>.py`.

## Ro'yxatga olish

`connectors/__init__.py` dagi import ro'yxatiga yangi modul qo'shiladi; manba yozuvi — migratsiya (seed) yoki
admin panel / `POST /api/admin/sources`.
