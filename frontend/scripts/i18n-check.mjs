// Barcha til fayllarida kalitlar bir xilmi, har xabar ICU sintaksisi to'g'rimi va uz-Cyrl.json uz.json bilan
// dolzarbmi (generator: python3 backend/scripts/gen_uz_cyrl_messages.py). Xato bo'lsa exit 1.
//   node scripts/i18n-check.mjs
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { IntlMessageFormat } = require("intl-messageformat");
const dir = new URL("../messages/", import.meta.url).pathname;
const LOCALES = ["uz", "uz-Cyrl", "ru", "en"];

const flat = (obj, prefix = "", out = {}) => {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") flat(v, key, out);
    else out[key] = v;
  }
  return out;
};

const data = Object.fromEntries(LOCALES.map((l) => [l, flat(JSON.parse(readFileSync(`${dir}${l}.json`, "utf8")))]));
let errors = 0;
const all = new Set(LOCALES.flatMap((l) => Object.keys(data[l])));
for (const key of [...all].sort()) {
  const missing = LOCALES.filter((l) => !(key in data[l]));
  if (missing.length) {
    console.log(`✗ ${key}: yo'q — ${missing.join(", ")}`);
    errors++;
  }
}
for (const l of LOCALES) {
  for (const [key, msg] of Object.entries(data[l])) {
    if (typeof msg !== "string") {
      console.log(`✗ ${l}:${key}: satr emas`);
      errors++;
      continue;
    }
    try {
      new IntlMessageFormat(msg, l.startsWith("uz") ? "uz" : l);
    } catch (e) {
      console.log(`✗ ${l}:${key}: ICU xato — ${e.message}`);
      errors++;
    }
  }
}
// uz-Cyrl.json — generatsiya qilingan fayl; uz.json o'zgarib, qayta yaratilmagan bo'lsa — xato
const gen = new URL("../../backend/scripts/gen_uz_cyrl_messages.py", import.meta.url).pathname;
const res = spawnSync("python3", [gen, "--check"], { encoding: "utf8" });
if (res.error) {
  console.log(`⚠ uz-Cyrl dolzarbligi tekshirilmadi (python3 yo'q: ${res.error.message})`);
} else if (res.status !== 0) {
  console.log(`✗ ${(res.stdout || res.stderr).trim()}`);
  errors++;
}
console.log(errors ? `XATO: ${errors}` : `OK: ${all.size} ta kalit × ${LOCALES.length} til`);
process.exit(errors ? 1 : 0);
