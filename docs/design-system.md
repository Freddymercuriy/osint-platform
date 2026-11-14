# Dizayn tizimi — OSINT Platform (v2)

Maqsad: **xavfsizlik mutaxassisi bo'lmagan odam ham har ekranni bir necha soniyada tushunsin.**
Uslub — toza, sokin, mazmun birinchi: bitta aksent rangi, oddiy kartalar, aniq matn. Bezak (aurora dog'lar, to'r fon,
radar, "scramble"/"reveal" matn, magnit/tilt, spotlight, sheen, harakatlanuvchi gradient) **ishlatilmaydi**.

Uchta tema — **Light / Dark / System** (standart: System) va uchta til — **o'zbek (lotin) / русский / English**.

## Fayllar
| Fayl | Nima |
|---|---|
| `frontend/app/globals.css` | Semantik tokenlar (CSS o'zgaruvchilar) — `:root` (light) va `.dark` qiymatlari; tone'lar (`.tone-*`) |
| `frontend/tailwind.config.ts` | Tokenlarni Tailwind ranglariga bog'lash (`bg-surface`, `text-fg-muted`, `border-border` ...) |
| `frontend/scripts/gen-tones.mjs` | `.tone-*` CSS bloklarini Tailwind palitrasidan yaratadi |
| `frontend/components/ui/index.tsx` | Umumiy komponentlar |
| `frontend/components/theme/*` | `ThemeProvider` (next-themes), `ThemeToggle`, `LocaleSwitcher` |
| `frontend/i18n/request.ts`, `frontend/messages/{uz,ru,en}.json` | next-intl: til cookie'dan, xabarlar |
| `frontend/lib/format.ts` | Sana/son formatlash (uz — qo'lda oy nomlari; ru/en — `Intl`) |
| `frontend/components/shell/*` | Sidebar, navigatsiya (`nav.ts`) |

## Tokenlar (faqat shular — `ink-*`, `slate-*`, `white/…`, `dark:` variantlar ishlatilmaydi)
| Token | Tailwind | Ma'nosi |
|---|---|---|
| `--bg` | `bg-bg` | sahifa foni |
| `--surface` | `bg-surface` | karta, panel, sidebar |
| `--surface-2` | `bg-surface-2` | hover, input foni, ichki blok |
| `--border`, `--border-strong` | `border-border`, `border-border-strong` | chegaralar |
| `--fg`, `--fg-muted`, `--fg-subtle` | `text-fg`, `text-fg-muted`, `text-fg-subtle` | asosiy / ikkinchi darajali / yordamchi matn |
| `--primary`, `--primary-fg`, `--primary-soft` | `bg-primary text-primary-fg`, `bg-primary-soft text-primary` | **yagona aksent** (tugma, havola, faol element) |
| `--ring` | `ring-ring` | fokus halqasi |
| `--success`, `--warning`, `--danger`, `--info` | `text-success` ... | holat ranglari |
| `.tone-<rang>` + `--tone-fg/bg/border` | `tone-red bg-tone-bg text-tone-fg border-tone-border` | nishonlar, kategoriya/jiddiylik ranglari |

Tone ranglari: `red orange amber yellow lime green emerald teal cyan sky blue indigo violet purple fuchsia pink rose slate`
(kategoriya rangi bazadan — `categories.color`). Light: matn 700, fon 50, chegara 200; Dark: matn 300, fon 950, chegara 800 —
ikkala temada WCAG AA kontrast.

**Jiddiylik** (severity): critical=red, high=orange, medium=amber, low=sky, info=slate.
**Manba holati**: ok=green, degraded=amber, down=red, blocked=purple, auth_missing=yellow, disabled/never_run=slate.
Rang hech qachon yolg'iz ma'no tashimaydi — doim matn (va kerak bo'lsa ikon) bilan.

Grafik ranglari — tokenlar orqali (`--chart-1..8`), tema almashganda grafik qayta chiziladi; bitta grafikda ≤ 8 rang.

## Tema
- `next-themes`: `attribute="class"`, standart `system`, sahifa yuklanishida "miltillash" yo'q.
- Almashtirgich (`ThemeToggle`, 3 holat: Light / Dark / System) — yuqori panelda va login sahifasida.
- Token qiymatlari temaga qarab o'zgaradi; komponentlarda `dark:` yozilmaydi.
- Chop etish hisoboti (`/report/[id]`) har doim yorug' (qog'oz).

## Til (i18n)
- `next-intl`, URL'da til prefiksi yo'q. Til cookie `NEXT_LOCALE` da va `users.locale` da; birinchi tashrifda brauzer
  tili, bo'lmasa `uz`.
- Hamma matn `messages/{uz,ru,en}.json` da (kalitlar uchala faylda bir xil — test tekshiradi). Komponentda
  `useTranslations("namespace")`; ko'plik — ICU (`{count, plural, one {...} few {...} many {...} other {...}}`, rus tili uchun shart).
- Sana/son: `useFormat()` (`lib/format.ts`). O'zbekcha oy nomlari qo'lda (brauzerlarda `uz-UZ` to'liq emas),
  ru/en — `Intl`. **`toLocaleDateString("uz-UZ")` ishlatilmaydi.**
- Hodisa matni interfeys tilida (`/api/events?lang=`), "Asl matn" tugmasi bilan; kategoriya nomlari bazadan (`name_uz/ru/en`).
- Backend xatolari: javobda `code` + tarjima qilingan `detail` (`Accept-Language`).

## Sahifa tuzilishi (hamma sahifada bir xil)
1. **Sarlavha** (`PageHeader title`) — nima ekanini aytadi.
2. **Bitta gap** (`description`) — sahifa nima uchun.
3. **Asosiy amal** (`actions`) — bitta asosiy tugma (`Button variant="primary"`), qolganlari `secondary`/`ghost`.
4. **Kontent.**
- Atamalar (CVE, IOC, TLP, baseline ...) uchun qisqa yordam matni yoki `title`/tooltip.
- Bo'sh holat: **bu yerda nima paydo bo'lishini** va **hozir nega bo'shligini** aytadi (`EmptyState title + description`).
- Yuklanish — `Skeleton`; xato — `ErrorBanner` (nima bo'ldi + nima qilish mumkin).
- Navigatsiya: **Umumiy ko'rinish**, **Hodisalar**, **Tekshiruvlar** (username, email, telefon, domen, tarix),
  **Admin** (faqat adminlar).

## Komponentlar (`@/components/ui`)
`Card` · `Button` (`primary|secondary|ghost|danger`, `sm|md|lg`, `loading`, `icon`) · `ButtonLink` · `Input` · `Select` ·
`Label` · `Badge` (`tone`) · `SeverityBadge` · `StatusBadge` · `IconBox` · `PageHeader` (`title`, `description`, `actions`,
`icon`) · `StatTile` · `EmptyState` · `ErrorBanner` · `Spinner` · `Skeleton` · `Logo`.
Ikonlar — `lucide-react` (emoji emas).

## Qoidalar
1. Kirish animatsiyasi — qisqa `animate-fade-in`; hover — rang/chegara o'tishi. `prefers-reduced-motion` hurmat qilinadi.
2. Fokus halqasi doim ko'rinadi (`focus-visible:ring-2 ring-ring`); hamma amal klaviatura bilan bajariladi
   (tugmalar `<button>`, havolalar `<a>`, ochiladigan menyular `Esc` bilan yopiladi).
3. Kontrast — WCAG AA (oddiy matn ≥ 4.5:1) ikkala temada.
4. Responsive: 360px dan; gorizontal skroll yo'q (smoke-test tekshiradi).
5. Tashqi havolalar: `target="_blank" rel="noreferrer"`.
6. Raqamlar `tabular-nums`; ID/hash/URL — `font-mono`.
