/* planskyline.js - EnergyWizards planvy "Skyline" (förvald) och val mellan den och planklockan (planclock.js).
 *
 * Dygnet framåt som en stad i skymning: ett hus per timme, husets höjd = elpriset (högt hus = dyr el). Fönstren lyser
 * när ditt hus använder el den timmen (bilen laddar, batteriet fylls, värmen går på) - starkare ju mer. Solprognosen är
 * solen som går upp och ner över staden, natten har stjärnor och måne. Bilarna är ljusstrimmor på vägen, batteriet är
 * reflexen i vattnet längst ner med sin nivå som linje. Dra fingret längs staden: glasrutan visar tid, pris och plan.
 *
 * Data: GET api/planclock (smartbox/plan_clock.py). Användning: EWPlanView.mount(element, data, { lang })
 */
(function () {
  "use strict";
  const T = {
    sv: { now: "Nu", today: "Idag", tomorrow: "Imorgon", sky: "Skyline", clock: "Klocka", charge: "Laddar", discharge: "Laddar ur",
          export: "Laddar ur · säljer", hold: "Sparas", idle: "Vilar", heatOn: "Värmer på", heatOff: "Värmen sänkt", nothing: "Inget särskilt",
          legend: ["Högt hus = dyr el", "Tänt fönster = huset använder el", "Batteriet", "Solen"] },
    en: { now: "Now", today: "Today", tomorrow: "Tomorrow", sky: "Skyline", clock: "Clock", charge: "Charging", discharge: "Discharging",
          export: "Discharging · selling", hold: "Holding", idle: "Idle", heatOn: "Pre-heating", heatOff: "Heat lowered", nothing: "Nothing special",
          legend: ["Tall building = expensive", "Lit window = house uses power", "Battery", "Sun"] },
  };
  const BATC = { charge: "#2dd4bf", discharge: "#f59e0b", export: "#e879f9", hold: "#94a3b8", idle: "#94a3b8" };
  const CARC = ["#a78bfa", "#60a5fa", "#f472b6", "#34d399"];
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let styled = false;
  function style() {
    if (styled) return;
    styled = true;
    const css = document.createElement("style");
    css.textContent = `
.ewsk{position:relative;border-radius:22px;overflow:hidden;isolation:isolate;background:#05070f;color:#eef2fb;box-shadow:0 0 0 1px rgba(255,255,255,.06)}
.ewsk svg{display:block;width:100%;height:auto;touch-action:pan-y;user-select:none;-webkit-user-select:none}
.ewsk .g{position:relative;padding:12px 14px 6px;background:linear-gradient(180deg,rgba(8,12,26,.95),rgba(8,12,26,.6));pointer-events:none}
.ewsk .k{font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;opacity:.65}
.ewsk .r{display:flex;align-items:baseline;gap:10px}.ewsk .t{font-size:1.9rem;font-weight:250;letter-spacing:-.03em;font-variant-numeric:tabular-nums;line-height:1.05}
.ewsk .p{font-size:.85rem;opacity:.8;font-variant-numeric:tabular-nums}
.ewsk .a{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;min-height:22px}
.ewsk .pill{font-size:.7rem;padding:2px 8px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);white-space:nowrap}
.ewsk-leg{display:flex;flex-wrap:wrap;gap:4px 12px;justify-content:center;font-size:.62rem;letter-spacing:.06em;opacity:.7;margin-top:8px}
.ewsk-leg i{display:inline-block;width:10px;height:3px;border-radius:2px;margin-right:5px;vertical-align:2px}
.ewpv-seg{display:flex;justify-content:flex-end;gap:4px;margin:0 0 8px}
.ewpv-seg button{font:inherit;font-size:.7rem;letter-spacing:.08em;padding:4px 10px;border-radius:999px;border:1px solid currentColor;background:transparent;color:inherit;opacity:.5;cursor:pointer}
.ewpv-seg button.on{opacity:1}`;
    document.head.appendChild(css);
  }

  function skyline(el, data, opts) {
    style();
    const L = T[opts.lang] || T.sv;
    const S = (data && data.slots) || [];
    if (!S.length) { el.innerHTML = ""; return null; }
    const N = S.length, cars = data.cars || [];
    const carCol = (id) => CARC[Math.max(0, cars.findIndex((c) => c.id === id)) % CARC.length];
    const carName = (id) => (cars.find((c) => c.id === id) || { name: id }).name;
    const P = S.map((s) => s.price).filter((v) => v != null), lo = Math.min(...P), hi = Math.max(...P);
    const lev = (p) => (p == null ? 0 : (p - lo) / Math.max(hi - lo, 1e-6));
    const sunMax = Math.max(1, ...S.map((s) => s.sun_w || 0));
    const hourOf = (i) => { const d = new Date(S[i].t); return d.getHours() + d.getMinutes() / 60; };
    const elev = (i) => Math.max((S[i].sun_w || 0) / sunMax, Math.max(0, Math.sin((hourOf(i) - 7) / 9 * Math.PI)) * 0.3);
    const hasBatEarly = S.some((s) => s.soc != null), carRows = Math.max(1, cars.length);
    const W = 480, GROUND = 250, H = GROUND + 12 + carRows * 9 + (hasBatEarly ? 52 : 6) + 16;
    const X = (i) => 8 + ((W - 16) * i) / (N - 1), f1 = (n) => n.toFixed(1);
    const mix = (a, b, t) => a.map((v, k) => Math.round(v + (b[k] - v) * t));
    const NIGHT = [6, 9, 26], DUSK = [70, 52, 110], DAY = [52, 96, 170];
    const sky = S.map((s, i) => { const e = elev(i), c = e < 0.15 ? mix(NIGHT, DUSK, e / 0.15) : mix(DUSK, DAY, Math.min(1, (e - 0.15) / 0.5));
      return `<stop offset="${(i / (N - 1) * 100).toFixed(2)}%" stop-color="rgb(${c})"/>`; }).join("");
    // "Användning" per kvart 0..1: bilarnas och batteriets laddeffekt plus värmepumpens billiga timmar
    const use = S.map((s) => Math.min(1, (Object.values(s.ev || {}).reduce((a, v) => a + (v || 0), 0) + (s.bat === "charge" ? Math.abs(s.bat_kw || 0) : 0)) / 8
      + (s.heat === "CHEAP" ? 0.25 : 0)));
    let bld = "", win = "", glow = "";
    const step = Math.max(1, Math.round(N / 24));                   // ett hus per timme
    for (let i = 0; i < N; i += step) {
      const grp = S.slice(i, i + step), p = grp.reduce((a, s) => a + (s.price || 0), 0) / grp.length;
      const u = Math.max(...use.slice(i, i + step)), x = X(i) + 0.8, w = X(Math.min(N - 1, i + step)) - X(i) - 1.6;
      const h = 28 + 175 * lev(p), y = GROUND - h;
      bld += `<rect x="${f1(x)}" y="${f1(y)}" width="${f1(w)}" height="${f1(h)}" fill="url(#ewskB)"/><rect x="${f1(x)}" y="${f1(y)}" width="${f1(w)}" height="1.2" fill="rgba(255,255,255,.18)"/>`;
      for (let r = y + 7; r < GROUND - 6; r += 8) for (let cx = x + 2.2; cx < x + w - 2.6; cx += 4.3) {
        const seed = (Math.floor(r) * 31 + Math.floor(cx) * 17 + i * 7) % 100;
        if (seed < 6 + u * 70) win += `<rect x="${f1(cx)}" y="${f1(r)}" width="2" height="2.8" fill="${u > 0.05 ? "#fde68a" : "#fef3c7"}" opacity="${u > 0.05 ? (0.55 + 0.45 * u).toFixed(2) : 0.28}"/>`;
      }
      if (grp.some((s) => s.heat === "CHEAP")) glow += `<rect x="${f1(x)}" y="${GROUND - 10}" width="${f1(w)}" height="10" fill="url(#ewskHeat)"/>`;
    }
    let stars = ""; for (let k = 0; k < 80; k++) { const x = (k * 83.1) % W, y = 18 + (k * 41.3) % 190, i = Math.round(x / W * (N - 1));
      if (elev(i) < 0.1) stars += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${k % 4 ? 0.6 : 1.1}" fill="#fff" opacity="${(0.25 + (k % 4) * 0.15).toFixed(2)}"/>`; }
    const nightI = S.findIndex((s, i) => elev(i) < 0.05 && i > 2);
    const moon = nightI > 0 ? `<g transform="translate(${f1(X(nightI) + 30)},46)" opacity=".85"><circle r="9" fill="#e5e7eb"/><circle r="9" cx="4" cy="-2" fill="rgb(${NIGHT})"/></g>` : "";
    const sunY = (i) => GROUND - 40 - 190 * ((S[i].sun_w || 0) / sunMax);
    const lanes = (test, col, y, h) => { let k = 0, o = ""; while (k < N) { if (!test(S[k])) { k++; continue; } let j = k; while (j + 1 < N && test(S[j + 1]) && col(S[j + 1]) === col(S[k])) j++;
      o += `<rect x="${f1(X(k))}" y="${y}" width="${f1(Math.max(3, X(Math.min(N - 1, j + 1)) - X(k)))}" height="${h}" rx="${h / 2}" fill="${col(S[k])}" filter="url(#ewskGlow)"/>`; k = j + 1; } return o; };
    const road = `<rect y="${GROUND}" width="${W}" height="${H - GROUND}" fill="#04060d"/><line x1="0" x2="${W}" y1="${GROUND + 10 + carRows * 9 + 4}" y2="${GROUND + 10 + carRows * 9 + 4}" stroke="rgba(255,255,255,.08)" stroke-dasharray="6 8"/>`;
    const carLanes = cars.map((c, k) => lanes((s) => (s.ev || {})[c.id] > 0.05, () => carCol(c.id), GROUND + 9 + k * 9, 3)).join("");
    const hasBat = hasBatEarly, batY = GROUND + 14 + carRows * 9 + 10;
    const bat = hasBat ? lanes((s) => ["charge", "discharge", "export"].includes(s.bat), (s) => BATC[s.bat], batY, 3)
      + `<path d="M${S.map((s, i) => `${f1(X(i))} ${f1(batY + 40 - 32 * ((s.soc || 0) / 100))}`).join(" L")}" fill="none" stroke="rgba(125,211,252,.75)" stroke-width="1.1"/>` : "";
    let ticks = ""; for (let i = 0; i < N; i += Math.max(1, step * 4)) ticks += `<text x="${f1(X(i) + (i ? 0 : 5))}" y="${H - 4}" font-size="9.5" letter-spacing=".5" fill="rgba(255,255,255,.55)" text-anchor="${i ? "middle" : "start"}">${i ? new Date(S[i].t).toTimeString().slice(0, 5) : L.now.toUpperCase()}</text>`;
    // Billigaste och dyraste timmen får en liten etikett ovanför sitt hus
    const hourly = []; for (let i = 0; i < N; i += step) { const grp = S.slice(i, i + step); hourly.push([i, grp.reduce((a, s) => a + (s.price || 0), 0) / grp.length]); }
    const cheap = hourly.reduce((a, b) => (b[1] < a[1] ? b : a)), dear = hourly.reduce((a, b) => (b[1] > a[1] ? b : a));
    const tag = ([i, p], col) => { const x = X(i) + (X(Math.min(N - 1, i + step)) - X(i)) / 2, y = GROUND - (28 + 175 * lev(p)) - 6;
      return `<text x="${f1(x)}" y="${f1(y)}" font-size="9" fill="${col}" text-anchor="middle">${p.toFixed(2).replace(".", opts.lang === "en" ? "." : ",")}</text>`; };
    const tags = tag(cheap, "#86efac") + tag(dear, "#fca5a5");
    // Soluppgången (första kvarten med solprognos efter natt) som en liten etikett vid horisonten
    let sunrise = "";
    const sr = S.findIndex((s, i) => i > 0 && (s.sun_w || 0) > 50 && (S[i - 1].sun_w || 0) <= 50);
    if (sr > 0 && (S[0].sun_w || 0) <= 50) sunrise = `<text x="${f1(X(sr))}" y="${GROUND - 4}" font-size="8.5" fill="#fcd34d" text-anchor="middle" opacity=".85">☀ ${new Date(S[sr].t).toTimeString().slice(0, 5)}</text>`;
    const nowMark = `<line x1="${f1(X(0))}" x2="${f1(X(0))}" y1="${GROUND - 210}" y2="${GROUND}" stroke="#fff" stroke-opacity=".35" stroke-dasharray="2 3"/>`;
    el.innerHTML = `<div class="ewsk"><div class="g"></div><svg viewBox="0 0 ${W} ${H}" role="slider" tabindex="0" aria-label="${esc(L.sky)}"><defs>
        <linearGradient id="ewskS" x1="0" x2="1">${sky}</linearGradient>
        <linearGradient id="ewskB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c2547"/><stop offset="1" stop-color="#0a0f22"/></linearGradient>
        <linearGradient id="ewskHeat" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fb923c" stop-opacity="0"/><stop offset="1" stop-color="#fb923c" stop-opacity=".45"/></linearGradient>
        <radialGradient id="ewskSun"><stop offset="0" stop-color="#fff7d6"/><stop offset=".3" stop-color="#fcd34d" stop-opacity=".8"/><stop offset="1" stop-color="#fcd34d" stop-opacity="0"/></radialGradient>
        <filter id="ewskBlur" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="18 0"/></filter>
        <filter id="ewskGlow" x="-50%" y="-300%" width="200%" height="700%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <rect x="-40" y="-20" width="${W + 80}" height="${GROUND + 40}" fill="url(#ewskS)" filter="url(#ewskBlur)"/>${stars}${moon}
      <g class="sun"><circle r="58" fill="url(#ewskSun)"/><circle r="10" fill="#fff7d6"/></g>
      ${nowMark}${bld}${win}${glow}${tags}${sunrise}${road}${carLanes}${bat}${ticks}
      <line class="cur" y1="0" y2="${H - 14}" stroke="rgba(255,255,255,.75)" stroke-width="1"/><circle class="nowd" cx="${f1(X(0))}" cy="${GROUND}" r="3" fill="#fff"/>
    </svg></div>
    <div class="ewsk-leg"><span><i style="background:#1c2547;height:8px"></i>${esc(L.legend[0])}</span><span><i style="background:#fde68a"></i>${esc(L.legend[1])}</span>
      ${cars.filter((c) => S.some((s) => (s.ev || {})[c.id] > 0.05)).map((c) => `<span><i style="background:${carCol(c.id)}"></i>${esc(c.name)}</span>`).join("")}
      ${hasBat ? `<span><i style="background:#2dd4bf"></i>${esc(L.legend[2])}</span>` : ""}${S.some((s) => s.sun_w > 50) ? `<span><i style="background:#fcd34d"></i>${esc(L.legend[3])}</span>` : ""}</div>`;
    const svg = el.querySelector("svg"), sun = el.querySelector(".sun"), cur = el.querySelector(".cur"), g = el.querySelector(".g");
    const day0 = new Date(S[0].t).getDate();
    const pills = (s) => {
      const o = [];
      if (s.bat && BATC[s.bat] && s.soc != null) o.push(`<span class="pill" style="border-color:${BATC[s.bat]}99">🔋 ${esc(L[s.bat])}${s.bat_kw ? " " + Math.abs(s.bat_kw).toFixed(1) + " kW" : ""} · ${s.soc} %</span>`);
      Object.entries(s.ev || {}).forEach(([c, kw]) => kw > 0.05 && o.push(`<span class="pill" style="border-color:${carCol(c)}99">🚗 ${esc(carName(c))} ${kw.toFixed(1)} kW</span>`));
      if (s.heat === "CHEAP") o.push(`<span class="pill">♨️ ${esc(L.heatOn)}</span>`); else if (s.heat === "EXPENSIVE") o.push(`<span class="pill">♨️ ${esc(L.heatOff)}</span>`);
      if ((s.sun_w || 0) > 50) o.push(`<span class="pill">☀ ${(s.sun_w / 1000).toFixed(1)} kW</span>`);
      return o.join("") || `<span class="pill" style="opacity:.6">${esc(L.nothing)}</span>`;
    };
    let idx = -1;
    const show = (i) => {
      i = Math.max(0, Math.min(N - 1, i));
      if (i === idx) return;
      idx = i;
      const s = S[i], x = X(i), sy = (s.sun_w || 0) > 30 ? sunY(i) : GROUND + 90;
      sun.setAttribute("transform", `translate(${f1(x)},${f1(sy)})`); sun.style.transition = "transform .18s ease-out";
      cur.setAttribute("x1", f1(x)); cur.setAttribute("x2", f1(x));
      const d = new Date(s.t), lab = i === 0 ? L.now : d.getDate() === day0 ? L.today : L.tomorrow;
      const price = s.price == null ? "–" : `${s.price.toFixed(2).replace(".", opts.lang === "en" ? "." : ",")} kr/kWh`;
      g.innerHTML = `<div class="k">${esc(lab)}</div><div class="r"><span class="t">${(i === 0 ? new Date() : d).toTimeString().slice(0, 5)}</span><span class="p">${price}</span></div><div class="a">${pills(s)}</div>`;
    };
    let raf = 0, want = 0, drag = false;
    const pick = (ev) => { const r = svg.getBoundingClientRect(); want = Math.round((ev.clientX - r.left) / r.width * (N - 1)); if (!raf) raf = requestAnimationFrame(() => { raf = 0; show(want); }); };
    svg.addEventListener("pointerdown", (e) => { drag = true; pick(e); });
    svg.addEventListener("pointermove", (e) => { if (drag || e.pointerType === "mouse") pick(e); });
    ["pointerup", "pointercancel", "pointerleave"].forEach((t) => svg.addEventListener(t, () => { drag = false; }));
    svg.addEventListener("keydown", (e) => { const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (d) { show(idx + d); e.preventDefault(); } });
    show(0);
    return { show, get index() { return idx; } };
  }

  // Planvyn: Skyline (förvald) eller planklockan - valet sparas i webbläsaren
  function mount(el, data, opts) {
    opts = opts || {};
    style();
    const L = T[opts.lang] || T.sv;
    let mode = "skyline";
    try { mode = localStorage.getItem("ew_planview") || "skyline"; } catch (e) { /* privat läge */ }
    if (mode === "clock" && !window.EWPlanClock) mode = "skyline";
    el.innerHTML = `<div class="ewpv-seg">${window.EWPlanClock ? `<button data-pv="skyline" class="${mode === "skyline" ? "on" : ""}">${esc(L.sky)}</button><button data-pv="clock" class="${mode === "clock" ? "on" : ""}">${esc(L.clock)}</button>` : ""}</div><div class="ewpv-body"></div>`;
    const body = el.querySelector(".ewpv-body");
    let h = mode === "clock" ? window.EWPlanClock.mount(body, data, opts) : skyline(body, data, opts);
    el.querySelectorAll("[data-pv]").forEach((b) => b.onclick = () => {
      try { localStorage.setItem("ew_planview", b.dataset.pv); } catch (e) { /* privat läge */ }
      mount(el, data, opts);
    });
    return { get index() { return h ? h.index : 0; } };
  }
  window.EWPlanView = { mount, skyline };
})();
