# Vendored: uztranslit (latin.jaybi.uz dvigateli)

| | |
|---|---|
| Manba | https://github.com/kool277/uz-latn-kiril — `core/python/uztranslit.py` (v1.3.0) |
| Commit | `ba20af5e326c20b76f623c4c193b4294f4576dc6` (2026-11-16 da olingan) |
| SHA-256 | `8f973ebd83206565eb88ca20c3577d432d52d7d0a1ab8b145bf11e07ca0f9b8e` |
| Litsenziya | MIT, Copyright (c) 2026 jaybi.uz — [`LICENSE.uztranslit`](LICENSE.uztranslit) |

https://latin.jaybi.uz saytining o'zi server API'siz (brauzerda, WebAssembly) ishlaydi — xuddi shu qoidalar
(`spec/SPEC.md`, 246 tekshiruv) bo'yicha yozilgan rasmiy Python porti shu yerga **o'zgartirishsiz** ko'chirilgan.
Tarmoqqa chiqmaydi, faqat standart kutubxona (`re`).

Ishlatish: `app/services/i18n/text.py` → `uz_to_cyrillic()` / `uz_to_latin()`.
Conformance: `tests/test_uztranslit_vendor.py` (`tests/fixtures/uztranslit_fixtures.json` — o'sha commit'dagi `spec/fixtures.json`).

Yangilash: yangi commit'dagi `core/python/uztranslit.py` va `spec/fixtures.json` ni almashtiring, jadvaldagi
commit/SHA-256 ni yangilang va testlarni ishga tushiring.
