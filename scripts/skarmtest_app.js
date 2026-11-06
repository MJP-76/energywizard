const puppeteer = require("puppeteer-core");
(async () => {
  const b = await puppeteer.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox", "--disable-gpu"] });
  const p = await b.newPage(); await p.setViewport({ width: +process.env.VW, height: +process.env.VH, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  const U = process.env.URL;
  await p.goto(U);
  await p.evaluate(async (pw) => fetch("api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user: "admin", password: pw }) }), process.env.WEB_PW || "");
  await p.evaluate(() => { localStorage.setItem("ew_primary", "tesla"); localStorage.setItem("ew_installed", "1"); localStorage.setItem("ew_theme", "dark"); localStorage.setItem("ew_page", "hem"); });
  await p.goto(U); await new Promise((r) => setTimeout(r, 5000));
  if (process.env.FS) await p.addStyleTag({ content: `html, body { font-size: ${process.env.FS}px !important; }` });
  await p.evaluate(() => window.dispatchEvent(new Event("resize"))); await new Promise((r) => setTimeout(r, 1200));
  await p.evaluate(() => { const pg = document.querySelector(".page"); if (pg) pg.scrollTop = 10000; }); await new Promise((r) => setTimeout(r, 500));
  await p.screenshot({ path: `/out/pg-hem-scrolled${process.env.TAG}.png` });
  for (const t of ["bil", "hus", "plan", "historik"]) {
    await p.evaluate((t) => { const b = document.querySelector(`[data-a="tab"][data-v="${t}"]`); if (b) b.click(); }, t);
    await new Promise((r) => setTimeout(r, 3500));
    await p.evaluate(() => window.dispatchEvent(new Event("resize"))); await new Promise((r) => setTimeout(r, 800));
    const info = await p.evaluate(() => { const pg = document.querySelector(".page"); const r = pg.getBoundingClientRect();
      const hidden = [...pg.querySelectorAll(".card")].filter((c) => c.offsetParent && c.getBoundingClientRect().height < 24).length;
      return { cls: pg.className, scroll: pg.scrollHeight - pg.clientHeight, tinyCards: hidden, hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth }; });
    await p.screenshot({ path: `/out/pg-${t}${process.env.TAG}.png` });
    console.log(process.env.TAG, t, JSON.stringify(info));
  }
  console.log("fel", JSON.stringify(errs));
  await b.close();
})();
