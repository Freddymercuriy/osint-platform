// Semantik tokenlar va tone'lar kontrastini ikkala temada tekshiradi (WCAG AA: oddiy matn ≥ 4.5).
//   node scripts/contrast-check.mjs
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const tones = readFileSync(new URL("../app/tones.css", import.meta.url), "utf8");

function block(src, selector) {
  const i = src.indexOf(`${selector} {`);
  const body = src.slice(i, src.indexOf("}", i));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*([\d\s]+);/g)].map((m) => [m[1], m[2].trim().split(/\s+/).map(Number)]));
}
const lum = ([r, g, b]) => {
  const f = (c) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
const ratio = (a, b) => {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};

const PAIRS = [
  ["fg", "bg"], ["fg", "surface"], ["fg", "surface-2"], ["fg-muted", "surface"], ["fg-muted", "surface-2"],
  ["fg-muted", "bg"], ["fg-subtle", "surface"], ["fg-subtle", "bg"], ["fg-subtle", "surface-2"],
  ["primary", "surface"], ["primary", "bg"], ["primary", "primary-soft"], ["primary-fg", "primary"],
  ["success", "surface"], ["warning", "surface"], ["danger", "surface"], ["info", "surface"],
];
let bad = 0;
for (const [theme, sel] of [["light", ":root"], ["dark", ".dark"]]) {
  const v = block(css, sel);
  for (const [a, b] of PAIRS) {
    const r = ratio(v[a], v[b]);
    if (r < 4.5) {
      bad++;
      console.log(`✗ ${theme}: ${a} / ${b} = ${r.toFixed(2)}`);
    }
  }
  const prefix = theme === "dark" ? ".dark .tone-" : ".tone-";
  for (const m of tones.matchAll(new RegExp(`^${prefix.replace(".", "\\.").replace(" ", " ")}([a-z]+) \\{([^}]*)\\}`, "gm"))) {
    const vars = Object.fromEntries([...m[2].matchAll(/--([\w-]+):\s*([\d\s]+);/g)].map((x) => [x[1], x[2].trim().split(/\s+/).map(Number)]));
    for (const bg of [vars["tone-bg"], v.surface]) {
      const r = ratio(vars["tone-fg"], bg);
      if (r < 4.5) {
        bad++;
        console.log(`✗ ${theme}: tone-${m[1]} fg = ${r.toFixed(2)}`);
      }
    }
  }
}
console.log(bad ? `XATO: ${bad} ta juftlik AA dan past` : "OK: barcha token va tone juftliklari ≥ 4.5:1 (ikkala tema)");
process.exit(bad ? 1 : 0);
