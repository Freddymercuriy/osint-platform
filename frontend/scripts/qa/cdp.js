// Headless Chrome'ni CDP orqali boshqaruvchi kichik drayver (puppeteer/playwright shart emas).
// Ishlatish: require("./cdp").run(async (p) => { await p.goto(url); await p.shot("nom"); })
// Chrome yo'li: CHROME_BIN (default /usr/bin/google-chrome). Skrinshotlar: frontend/.qa-shots/
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");
// Next o'zi bilan olib keladigan ws — alohida paket o'rnatish shart emas
const WebSocket = require("next/dist/compiled/ws");

const PORT = Number(process.env.CDP_PORT || 9333);
const OUT = path.join(__dirname, "..", "..", ".qa-shots");
fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const getJson = (url) =>
  new Promise((res, rej) => {
    const req = http.request(url, (r) => {
      let d = "";
      r.on("data", (c) => (d += c));
      r.on("end", () => {
        try {
          res(JSON.parse(d));
        } catch (e) {
          rej(e);
        }
      });
    });
    req.on("error", rej);
    req.end();
  });

async function run(fn) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "osint-qa-chrome-"));
  const chrome = spawn(
    process.env.CHROME_BIN || "/usr/bin/google-chrome",
    [
      "--headless=new",
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--disable-gpu",
      "--hide-scrollbars",
      "--window-size=1440,900",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  let exitCode = 0;
  try {
    let target;
    for (let i = 0; i < 50 && !target; i++) {
      try {
        const list = await getJson(`http://127.0.0.1:${PORT}/json`);
        target = list.find((t) => t.type === "page");
      } catch {
        /* chrome hali tayyor emas */
      }
      if (!target) await sleep(200);
    }
    if (!target) throw new Error("Chrome ishga tushmadi");
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((r, j) => {
      ws.on("open", r);
      ws.on("error", j);
    });
    let id = 0;
    const pending = new Map();
    const logs = [];
    ws.on("message", (m) => {
      const msg = JSON.parse(m);
      if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) rej(new Error(msg.error.message));
        else res(msg.result);
        return;
      }
      if (msg.method === "Runtime.consoleAPICalled") {
        const t = msg.params.type;
        if (t === "error" || t === "warning") {
          const text = msg.params.args.map((a) => a.value ?? a.description ?? "").join(" ");
          logs.push(`[console.${t}] ${text}`.slice(0, 600));
        }
      } else if (msg.method === "Runtime.exceptionThrown") {
        const d = msg.params.exceptionDetails;
        logs.push(`[exception] ${d.text} ${d.exception?.description ?? ""}`.slice(0, 600));
      } else if (msg.method === "Log.entryAdded") {
        const e = msg.params.entry;
        if (e.level === "error") logs.push(`[log.error] ${e.text} ${e.url ?? ""}`.slice(0, 400));
      }
    });
    const send = (method, params = {}) =>
      new Promise((res, rej) => {
        const i = ++id;
        pending.set(i, { res, rej });
        ws.send(JSON.stringify({ id: i, method, params }));
      });

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Log.enable");

    const p = {
      send,
      sleep,
      /** konsol xatolari/ogohlantirishlari (o'qib bo'lgach `logs.splice(0)` bilan tozalang) */
      logs,
      async viewport(width, height, mobile = false) {
        await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: mobile ? 2 : 1, mobile });
      },
      /** Tema (next-themes localStorage "theme"): light | dark | system */
      async theme(value) {
        if (p._themeScript) await send("Page.removeScriptToEvaluateOnNewDocument", { identifier: p._themeScript });
        const r = await send("Page.addScriptToEvaluateOnNewDocument", {
          source: `try{localStorage.setItem('theme', ${JSON.stringify(value)})}catch(e){}`,
        });
        p._themeScript = r.identifier;
      },
      /** Interfeys tili — next-intl cookie'si (server tomonda o'qiladi) */
      async locale(value, base) {
        await send("Network.enable");
        await send("Network.setCookie", { name: "NEXT_LOCALE", value, url: base });
      },
      /** JWT'ni har bir sahifa yuklanishidan oldin localStorage'ga qo'yadi */
      async token(tok) {
        await send("Page.addScriptToEvaluateOnNewDocument", {
          source: `try{localStorage.setItem('osint_token', ${JSON.stringify(tok)})}catch(e){}`,
        });
      },
      async goto(url, wait = 1500) {
        await send("Page.navigate", { url });
        for (let i = 0; i < 100; i++) {
          if ((await p.eval("document.readyState")) === "complete") break;
          await sleep(100);
        }
        await sleep(wait);
      },
      async eval(expression) {
        const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
        if (r.exceptionDetails) {
          throw new Error("eval: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
        }
        return r.result.value;
      },
      async waitFor(expression, timeout = 30000) {
        const t0 = Date.now();
        while (Date.now() - t0 < timeout) {
          if (await p.eval(expression)) return true;
          await sleep(200);
        }
        throw new Error("waitFor vaqti tugadi: " + expression);
      },
      /** React input'iga matn yozish (fokus + insertText) */
      async type(selector, text) {
        await p.eval(
          `(()=>{const el=document.querySelector(${JSON.stringify(selector)}); el.focus(); el.select&&el.select(); return true})()`,
        );
        await send("Input.insertText", { text });
      },
      async click(selector) {
        return p.eval(
          `(()=>{const el=document.querySelector(${JSON.stringify(selector)}); if(!el) return false; el.click(); return true})()`,
        );
      },
      async clickText(text, tag = "button") {
        return p.eval(
          `(()=>{const el=[...document.querySelectorAll(${JSON.stringify(tag)})].find(e=>e.textContent.trim().includes(${JSON.stringify(text)})); if(!el) return false; el.click(); return true})()`,
        );
      },
      /** PNG skrinshot; full=true — butun sahifa (6000px gacha) */
      async shot(name, full = false) {
        const params = { format: "png" };
        if (full) {
          const s = (await send("Page.getLayoutMetrics")).cssContentSize;
          params.captureBeyondViewport = true;
          params.clip = { x: 0, y: 0, width: s.width, height: Math.min(s.height, 6000), scale: 1 };
        }
        const r = await send("Page.captureScreenshot", params);
        const f = path.join(OUT, name + ".png");
        fs.writeFileSync(f, Buffer.from(r.data, "base64"));
        return f;
      },
      /** Gorizontal skroll bormi: sw > vw bo'lsa sahifa yon tomonga suriladi */
      async overflow() {
        return p.eval(
          "({vw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth})",
        );
      },
    };
    await fn(p);
    ws.close();
  } catch (e) {
    console.error("XATO:", e.message);
    exitCode = 1;
  } finally {
    chrome.kill("SIGKILL");
    await sleep(300);
    // faqat o'zimiz mkdtemp bilan yaratgan vaqtinchalik profil
    fs.rmSync(profile, { recursive: true, force: true });
  }
  process.exit(exitCode);
}

module.exports = { run };
