// UI smoke-test: barcha sahifalarni desktop (1440px) va mobil (360px) da ochadi; konsol xatolari,
// gorizontal skroll va ko'rinmay qolgan kontentni tekshiradi; skrinshotlarni frontend/.qa-shots/ ga yozadi.
//
// Ishga tushirish (dev server va backend ishlab turgan bo'lishi kerak):
//   cd frontend
//   TOKEN=<JWT> node scripts/qa/smoke.js        # BASE=http://localhost:3000, API=http://localhost:8000 (default)
// JWT olish: POST /api/auth/login (username=<email>&password=<parol>) → access_token.
// TOKEN berilmasa faqat ochiq sahifalar tekshiriladi. Muammo topilsa exit code 1.
const { run } = require("./cdp");

const BASE = process.env.BASE || "http://localhost:3000";
const TOKEN = process.env.TOKEN || "";
const API = process.env.API || "http://localhost:8000";
const PUBLIC = ["/", "/login", "/register"];
const PRIVATE = [
  "/dashboard",
  "/dashboard/events",
  "/dashboard/username",
  "/dashboard/email",
  "/dashboard/phone",
  "/dashboard/domain",
  "/dashboard/history",
];
const VIEWPORTS = [
  ["desktop", 1440, 900, false],
  ["mobile", 360, 740, true],
];

// Matni bor, lekin shaffof qolib ketgan elementlar (scroll-reveal ishlamay qolsa)
const HIDDEN_JS = `[...document.querySelectorAll("main *, article *")].filter((el) =>
  parseFloat(getComputedStyle(el).opacity) < 0.05 &&
  el.textContent.trim().length > 3 &&
  el.getBoundingClientRect().height > 10).length`;

run(async (p) => {
  if (TOKEN) await p.token(TOKEN);
  else console.log("TOKEN berilmagan: faqat ochiq sahifalar tekshiriladi");
  const pages = TOKEN ? [...PUBLIC, ...PRIVATE] : PUBLIC;
  // Hisobot sahifasi: tarixdagi eng so'nggi qidiruv bo'yicha (tarix bo'sh bo'lsa o'tkazib yuboriladi)
  if (TOKEN) {
    try {
      const res = await fetch(`${API}/api/search/history?limit=1`, { headers: { Authorization: `Bearer ${TOKEN}` } });
      const [job] = await res.json();
      if (job?.id) pages.push(`/report/${job.id}`);
      else console.log("Tarix bo'sh: /report sahifasi tekshirilmadi");
    } catch (e) {
      console.log("Tarixni olib bo'lmadi, /report tekshirilmadi: " + e.message);
    }
  }
  let problems = 0;

  for (const [label, w, h, mobile] of VIEWPORTS) {
    await p.viewport(w, h, mobile);
    for (const url of pages) {
      await p.goto(BASE + url, 2500);
      // foydalanuvchi kabi aylantiramiz: scroll-reveal animatsiyalari ishga tushsin
      const height = await p.eval("document.documentElement.scrollHeight");
      for (let y = 0; y < height; y += 500) {
        await p.eval(`window.scrollTo(0, ${y})`);
        await p.sleep(250);
      }
      await p.sleep(600);
      const hidden = await p.eval(HIDDEN_JS);
      const o = await p.overflow();
      await p.eval("window.scrollTo(0, 0)");
      await p.sleep(300);
      const slug = url === "/" ? "home" : url.slice(1).split("/").join("-");
      await p.shot(`${label}-${slug}`, true);

      const issues = p.logs.splice(0);
      const scrolls = o.sw > o.vw;
      const bad = issues.length > 0 || scrolls || hidden > 0;
      if (bad) problems++;
      console.log(
        `${bad ? "✗" : "✓"} ${label.padEnd(7)} ${url.padEnd(22)} konsol=${issues.length} ` +
          `skroll=${scrolls ? "GORIZONTAL" : "ok"} yashirin=${hidden}`,
      );
      for (const i of issues) console.log("     " + i);
    }
  }

  console.log("");
  if (problems) throw new Error(`${problems} ta sahifada muammo topildi`);
  console.log("Hammasi toza");
});
