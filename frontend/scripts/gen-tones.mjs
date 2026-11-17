// `.tone-*` CSS bloklarini Tailwind palitrasidan yaratadi (light: 700/50/200, dark: 300/950/800).
// Ishga tushirish: node scripts/gen-tones.mjs > app/tones.css
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const colors = require("tailwindcss/colors");

const TONES = ["red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
  "indigo", "violet", "purple", "fuchsia", "pink", "rose", "slate"];

const rgb = (hex) => {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).join(" ");
};

const out = ["/* Avtomatik yaratilgan: node scripts/gen-tones.mjs > app/tones.css — qo'lda tahrirlamang */"];
for (const t of TONES) {
  const c = colors[t];
  out.push(`.tone-${t} { --tone-fg: ${rgb(c[700])}; --tone-bg: ${rgb(c[50])}; --tone-border: ${rgb(c[200])}; --tone-solid: ${rgb(c[600])}; }`);
}
for (const t of TONES) {
  const c = colors[t];
  out.push(`.dark .tone-${t} { --tone-fg: ${rgb(c[300])}; --tone-bg: ${rgb(c[950])}; --tone-border: ${rgb(c[800])}; --tone-solid: ${rgb(c[400])}; }`);
}
console.log(out.join("\n"));
