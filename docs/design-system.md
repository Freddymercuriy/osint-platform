# Dizayn tizimi — OSINT.uz

Uslub: **qorong'i "intelligence center"** — chuqur navy fon, nozik kiber-to'r, shisha (glass) kartalar,
cyan → violet → fuchsia gradient aksent, monospace texnik yorliqlar, o'lchovli animatsiya.

## Fayllar
| Fayl | Nima |
|---|---|
| `frontend/tailwind.config.ts` | ranglar (`ink-*`, `brand-*`), shriftlar, soyalar, animatsiyalar |
| `frontend/app/globals.css` | fon (to'r + nur), `.glass`, `.glass-hover`, `.text-gradient`, `.gradient-border`, `.skeleton`, `.kbd` |
| `frontend/components/ui/index.tsx` | barcha umumiy komponentlar (pastda) |
| `frontend/lib/categories.ts` | Events kategoriyalari: nom, rang (tone), ikon — butun UI'da bir xil |
| `frontend/components/shell/*` | Sidebar, navigatsiya (`nav.ts`) |
| `frontend/app/dashboard/layout.tsx` | dashboard qobig'i: sidebar + yuqori panel (🔔). Sahifalar faqat `<main>` ichini chizadi |

## Ranglar
- Fon: `ink-950` (sahifa), `ink-900` (panel), `ink-850` (karta), `ink-800` (input/hover), chegaralar `white/[0.06]`–`white/10`.
- Aksent: `brand-cyan #22d3ee`, `brand-violet #8b5cf6`, `brand-fuchsia #d946ef`; gradient: `bg-brand-gradient`, matn: `.text-gradient`.
- Matn: sarlavha `text-white`, asosiy `text-slate-200`, ikkinchi darajali `text-slate-400`, sokin `text-slate-500/600`.
- Tone'lar (Badge/IconBox): `cyan sky violet fuchsia red orange amber emerald slate`.
- Kategoriya ranglari (o'zgartirma): ransomware=red, leak=orange, telegram=sky, tg_group=violet, news=slate.
- Holat: found=emerald, not_found=slate, error/noaniq=amber. Rang hech qachon yolg'iz ma'no tashimaydi — doim ikon + matn.

## Tipografiya
- `font-sans` (Inter), `font-mono` (JetBrains Mono) — raqamlar, ID, yorliqlar, "eyebrow" uchun.
- Sahifa sarlavhasi `PageHeader` orqali (2xl/3xl, semibold). Eyebrow: mono, uppercase, `tracking-[0.2em]`.
- Raqamlar: `font-mono tabular-nums`.

## Komponentlar (`@/components/ui`)
`Card` (glass; `hover`, `glow`) · `Button` (`primary|secondary|ghost|danger`, `sm|md|lg`, `loading`, `icon`) · `ButtonLink` ·
`Input` (`icon`, `mono`, `inputSize="lg"`) · `Label` · `Badge` (`tone`, `icon`) · `CategoryBadge` · `StatusBadge` ·
`IconBox` · `PageHeader` (`icon`, `tone`, `eyebrow`, `title`, `subtitle`, `actions`) · `StatTile` · `EmptyState` ·
`ErrorBanner` · `Spinner` · `Skeleton` · `LiveDot` · `Logo` · `timeAgo()`.
Ikonlar: **`lucide-react`** (emoji ishlatilmaydi).

## Qoidalar
1. Har sahifa: `PageHeader` → kontent kartalari. Bo'sh holat `EmptyState`, xato `ErrorBanner`, yuklanish `Skeleton`/`Spinner`.
2. Kartalar orasidagi bo'shliq `gap-4`/`gap-6`; ichki padding `p-5`/`p-6`.
3. Animatsiya: kirishda `animate-fade-in` (ro'yxatlarda `style={{animationDelay}}` bilan zinapoya), hover o'tishlari. `prefers-reduced-motion` globalda hurmat qilinadi.
4. Responsive: 360px dan; grid'lar `sm:`/`lg:` bilan.
5. Tashqi havolalar: `target="_blank" rel="noreferrer"`.
6. Matnlar o'zbek (lotin) tilida.
7. Grafiklar: `docs/design-system.md` dagi ranglardan alohida — bitta qatorli grafik bitta rangda (`#3987e5`), hover tooltip, nozik chiziq, ortiqcha yorliq yo'q.
