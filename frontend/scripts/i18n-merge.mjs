// Asosiy manba — messages/{uz,ru,en}.json. Parallel ishlaganda har kim o'z namespace'ini
// messages/parts/<namespace>.<locale>.json ga yozadi, keyin: node scripts/i18n-merge.mjs (va parts o'chiriladi).
import { readFileSync, readdirSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const dir = new URL("../messages/", import.meta.url).pathname;
const LOCALES = ["uz", "ru", "en"];
for (const locale of LOCALES) {
  const file = join(dir, `${locale}.json`);
  const base = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : {};
  const partsDir = join(dir, "parts");
  if (existsSync(partsDir)) {
    for (const f of readdirSync(partsDir).sort()) {
      const m = f.match(/^([\w-]+)\.(uz|ru|en)\.json$/);
      if (!m || m[2] !== locale) continue;
      base[m[1]] = JSON.parse(readFileSync(join(partsDir, f), "utf8"));
    }
  }
  const sorted = Object.fromEntries(Object.keys(base).sort().map((k) => [k, base[k]]));
  writeFileSync(file, JSON.stringify(sorted, null, 2) + "\n");
}
console.log("messages birlashtirildi");
