// Uchala til faylida kalitlar bir xilmi va har xabar ICU sintaksisi to'g'rimi. Xato bo'lsa exit 1.
//   node scripts/i18n-check.mjs
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { IntlMessageFormat } = require("intl-messageformat");
const dir = new URL("../messages/", import.meta.url).pathname;
const LOCALES = ["uz", "ru", "en"];

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
      new IntlMessageFormat(msg, l === "uz" ? "uz" : l);
    } catch (e) {
      console.log(`✗ ${l}:${key}: ICU xato — ${e.message}`);
      errors++;
    }
  }
}
console.log(errors ? `XATO: ${errors}` : `OK: ${all.size} ta kalit × ${LOCALES.length} til`);
process.exit(errors ? 1 : 0);
