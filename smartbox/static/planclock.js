/* planclock.js - EnergyWizards dragbara planklocka (webben och mobilappen).
 *
 * En 24-timmarsurtavla: en stapel per kvart, längden efter priset och färgen efter vad som händer då
 * (batteriet laddar/laddar ur, en bil laddar, annars prisnivån). Solprognosen ligger som en mjuk gul krans utanför.
 * Visaren pulserar på "nu" och går att dra (mus, finger, piltangenter) till valfri kvart de närmaste 24 timmarna -
 * mitten visar då klockslag, pris och vad batteri och bilar gör just då. Släpp och tryck "Nu" för att gå tillbaka.
 *
 * Data: GET api/planclock (smartbox/plan_clock.py). Användning:
 *   EWPlanClock.mount(element, data, { unit: "kr", lang: "sv" })
 * Ingen beroende kod - bara SVG och pekarhändelser.
 */
(function () {
  "use strict";
  const COL = { discharge: "#f59e0b", export: "#d946ef", charge: "#2dd4bf", hold: "#64748b", idle: "#475569", car: ["#a78bfa", "#f472b6", "#60a5fa", "#34d399"],
                cheap: "#3fb68b", mid: "#7c8aa0", dear: "#e0675e", sun: "#facc15" };
  const T = {
    sv: { now: "Nu", today: "Idag", tomorrow: "Imorgon", discharge: "Batteriet laddar ur", export: "Batteriet laddar ur och säljer", charge: "Batteriet laddar", hold: "Batteriet sparas",
          idle: "Batteriet vilar", auto: "Batteriet: självförbrukning", charges: "laddar", sun: "Sol", nothing: "Inget planerat",
          heat: { CHEAP: "Värmepumpen värmer på (billigt)", EXPENSIVE: "Värmepumpen sänkt (dyrt)" }, drag: "Dra visaren för att se planen",
          legend: ["Laddar ur", "Laddar", "Bil", "Solprognos"], cheap: "Billigt", dear: "Dyrt" },
    en: { now: "Now", today: "Today", tomorrow: "Tomorrow", discharge: "Battery discharges", export: "Battery discharges and sells", charge: "Battery charges", hold: "Battery holds",
          idle: "Battery idle", auto: "Battery: self-consumption", charges: "charges", sun: "Sun", nothing: "Nothing planned",
          heat: { CHEAP: "Heat pump pre-heats (cheap)", EXPENSIVE: "Heat pump lowered (expensive)" }, drag: "Drag the hand to explore the plan",
          legend: ["Discharging", "Charging", "Car", "Sun forecast"], cheap: "Cheap", dear: "Expensive" },
  };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let styled = false;
  function style() {
    if (styled) return;
    styled = true;
    const css = document.createElement("style");
    css.textContent = `
.ewpc{position:relative;max-width:420px;margin:0 auto;user-select:none;-webkit-user-select:none;touch-action:none;container-type:inline-size}
.ewpc svg{width:100%;height:auto;display:block;overflow:visible}
.ewpc .ewpc-mid{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;text-align:center;padding:0 30%}
.ewpc .ewpc-day{font-size:clamp(.55rem,2.6cqw,.7rem);letter-spacing:.12em;text-transform:uppercase;opacity:.6;min-height:1em}
.ewpc .ewpc-time{font-size:clamp(1.5rem,10cqw,2.8rem);font-weight:700;font-variant-numeric:tabular-nums;line-height:1.05}
.ewpc .ewpc-price{font-size:clamp(.62rem,3cqw,.8rem);opacity:.75;font-variant-numeric:tabular-nums}
.ewpc .ewpc-act{font-size:clamp(.56rem,2.7cqw,.72rem);margin-top:4px;line-height:1.35;font-weight:600}
.ewpc .ewpc-now{position:absolute;right:4%;top:2%;border:1px solid currentColor;background:transparent;color:inherit;border-radius:999px;padding:4px 12px;font:inherit;font-size:.75rem;opacity:.8;cursor:pointer}
.ewpc .ewpc-now[hidden]{display:none}
.ewpc-legend{display:flex;flex-wrap:wrap;gap:6px 14px;justify-content:center;font-size:.72rem;opacity:.75;margin-top:6px}
.ewpc-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.ewpc-hint{text-align:center;font-size:.7rem;opacity:.5;margin-top:2px}
.ewpc .ewpc-pulse{transform-box:fill-box;transform-origin:center;animation:ewpcPulse 1.8s ease-out infinite}
@keyframes ewpcPulse{0%{opacity:.75;transform:scale(1)}100%{opacity:0;transform:scale(3.2)}}
@media (prefers-reduced-motion:reduce){.ewpc .ewpc-pulse{animation:none;opacity:0}}
.ewpc .ewpc-hand{cursor:grab}.ewpc.drag .ewpc-hand{cursor:grabbing}`;
    document.head.appendChild(css);
  }

  function mount(el, data, opts) {
    style();
    opts = opts || {};
    const L = T[opts.lang] || T.sv, unit = opts.unit || "kr";
    const slots = (data && data.slots) || [];
    if (!slots.length) { el.innerHTML = ""; return null; }
    const cars = (data.cars || []).map((c, k) => ({ id: c.id, name: c.name || c.id, col: COL.car[k % COL.car.length] }));
    const carCol = (id) => (cars.find((c) => c.id === id) || { col: COL.car[0] }).col;
    const carName = (id) => (cars.find((c) => c.id === id) || { name: id }).name;
    const C = 200, R0 = 112, R1 = 168;                 // stapelns inner- och maxradie
    const prices = slots.map((s) => s.price).filter((v) => v != null);
    const lo = Math.min(...prices), hi = Math.max(...prices), span = Math.max(hi - lo, 1e-6);
    const sunMax = Math.max(1, ...slots.map((s) => s.sun_w || 0));
    const t0 = new Date(slots[0].t);
    const angOf = (d) => ((d.getHours() + d.getMinutes() / 60) / 24) * 2 * Math.PI - Math.PI / 2;
    const pt = (a, r) => [C + r * Math.cos(a), C + r * Math.sin(a)];
    const f1 = (n) => n.toFixed(1);
    const level = (p) => (p - lo) / span;
    const priceCol = (p) => (p == null ? COL.idle : level(p) < 0.33 ? COL.cheap : level(p) < 0.66 ? COL.mid : COL.dear);
    const slotCol = (s) => {
      if (s.bat === "discharge") return COL.discharge;
      if (s.bat === "export") return COL.export;
      if (s.bat === "charge") return COL.charge;
      const car = Object.keys(s.ev || {}).find((k) => (s.ev[k] || 0) > 0.05);
      if (car) return carCol(car);
      return priceCol(s.price);
    };
    let svg = `<svg viewBox="0 0 400 400" role="slider" tabindex="0" aria-label="${esc(L.drag)}" aria-valuemin="0" aria-valuemax="${slots.length - 1}">`;
    // Solkransen: en mjuk yta utanför staplarna, tjockare där prognosen är högre
    let sunPath = "";
    const sunPts = [];
    slots.forEach((s) => {
      const w = s.sun_w || 0;
      if (w > sunMax * 0.04) sunPts.push([angOf(new Date(s.t)), 6 + 16 * (w / sunMax)]);
      else if (sunPts.length && sunPts[sunPts.length - 1] !== null) sunPts.push(null);
    });
    const runs = [];
    let cur = [];
    sunPts.forEach((p) => { if (p === null) { if (cur.length) runs.push(cur); cur = []; } else cur.push(p); });
    if (cur.length) runs.push(cur);
    runs.forEach((run) => {
      if (run.length < 2) return;
      const outer = run.map(([a, h]) => pt(a, R1 + 6 + h)), inner = run.slice().reverse().map(([a]) => pt(a, R1 + 4));
      sunPath += `<path d="M${outer.map((p) => p.map(f1).join(" ")).join(" L")} L${inner.map((p) => p.map(f1).join(" ")).join(" L")} Z" fill="${COL.sun}" opacity=".28"/>`;
      sunPath += `<path d="M${outer.map((p) => p.map(f1).join(" ")).join(" L")}" fill="none" stroke="${COL.sun}" stroke-width="1.4" stroke-dasharray="2 3" opacity=".8"/>`;
    });
    svg += sunPath;
    svg += `<circle cx="${C}" cy="${C}" r="${R0 - 24}" fill="none" stroke="currentColor" stroke-opacity=".08"/>`;
    // Kvartsstaplarna
    slots.forEach((s, i) => {
      const a = angOf(new Date(s.t)), len = s.price == null ? 6 : 10 + (R1 - R0 - 10) * level(s.price);
      const [x1, y1] = pt(a, R0), [x2, y2] = pt(a, R0 + len);
      const strong = s.bat === "charge" || s.bat === "discharge" || s.bat === "export" || Object.values(s.ev || {}).some((v) => v > 0.05);
      svg += `<line data-i="${i}" x1="${f1(x1)}" y1="${f1(y1)}" x2="${f1(x2)}" y2="${f1(y2)}" stroke="${slotCol(s)}" stroke-width="${strong ? 4.2 : 3.2}" stroke-linecap="round" opacity="${strong ? 1 : 0.55}"/>`;
    });
    // Timsiffror
    for (let h = 0; h < 24; h++) {
      const a = (h / 24) * 2 * Math.PI - Math.PI / 2, [x, y] = pt(a, R0 - 13), big = h % 6 === 0;
      svg += `<text x="${f1(x)}" y="${f1(y + 3.5)}" text-anchor="middle" font-size="${big ? 11 : 9}" font-weight="${big ? 700 : 400}" fill="currentColor" opacity="${big ? 0.7 : 0.4}">${String(h).padStart(2, "0")}</text>`;
    }
    // "Nu"-markering (pulserar) och den dragbara visaren
    const aNow = angOf(t0), [nx, ny] = pt(aNow, R1 + 2);
    svg += `<circle cx="${f1(nx)}" cy="${f1(ny)}" r="4" fill="currentColor" class="ewpc-pulse"/><circle cx="${f1(nx)}" cy="${f1(ny)}" r="3" fill="currentColor"/>`;
    svg += `<g class="ewpc-hand"><line class="ewpc-hl" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle class="ewpc-hk" r="9" fill="currentColor" fill-opacity=".15" stroke="currentColor" stroke-width="2"/></g>`;
    svg += `</svg>`;
    const legend = [[COL.cheap, L.cheap], [COL.dear, L.dear]].concat([[COL.discharge, L.legend[0]], [COL.charge, L.legend[1]]].filter(() => data.has_battery))
      .concat(slots.some((s) => s.bat === "export") ? [[COL.export, L.export]] : [])
      .concat(cars.map((c) => [c.col, c.name])).concat(slots.some((s) => s.sun_w) ? [[COL.sun, L.legend[3]]] : []);
    el.innerHTML = `<div class="ewpc">${svg}<div class="ewpc-mid"><div class="ewpc-day"></div><div class="ewpc-time"></div><div class="ewpc-price"></div><div class="ewpc-act"></div></div>
      <button class="ewpc-now" type="button" hidden>${esc(L.now)}</button></div>
      <div class="ewpc-legend">${legend.map(([c, t]) => `<span><i style="background:${c}"></i>${esc(t)}</span>`).join("")}</div><div class="ewpc-hint">${esc(L.drag)}</div>`;
    const root = el.querySelector(".ewpc"), svgEl = root.querySelector("svg"), hl = root.querySelector(".ewpc-hl"), hk = root.querySelector(".ewpc-hk");
    const mid = { day: root.querySelector(".ewpc-day"), time: root.querySelector(".ewpc-time"), price: root.querySelector(".ewpc-price"), act: root.querySelector(".ewpc-act") };
    const nowBtn = root.querySelector(".ewpc-now");
    let idx = 0;
    const fmtPrice = (p) => (p == null ? "–" : unit === "öre" ? `${Math.round(p * 100)} öre/kWh` : `${p.toFixed(2).replace(".", opts.lang === "en" ? "." : ",")} ${unit}/kWh`);
    function show(i, fromUser) {
      i = Math.max(0, Math.min(slots.length - 1, i));
      if (i === idx && fromUser) return;
      idx = i;
      const s = slots[i], d = new Date(s.t), a = angOf(d);
      const [x1, y1] = pt(a, R0 - 26), [x2, y2] = pt(a, R1 + 2);     // visaren börjar utanför texten i mitten
      hl.setAttribute("x1", f1(x1)); hl.setAttribute("y1", f1(y1)); hl.setAttribute("x2", f1(x2)); hl.setAttribute("y2", f1(y2));
      hk.setAttribute("cx", f1(x2)); hk.setAttribute("cy", f1(y2));
      svgEl.setAttribute("aria-valuenow", i);
      const sameDay = d.toDateString() === t0.toDateString();
      mid.day.textContent = i === 0 ? L.now : sameDay ? L.today : L.tomorrow;
      mid.time.textContent = i === 0 ? t0.toTimeString().slice(0, 5) : d.toTimeString().slice(0, 5);
      mid.price.textContent = fmtPrice(s.price);
      const acts = [];
      if (s.bat && T.sv[s.bat] !== undefined) {
        let t = L[s.bat] || s.bat;
        if (s.bat_kw != null && (s.bat === "charge" || s.bat === "discharge" || s.bat === "export")) t += ` · ${Math.abs(s.bat_kw).toFixed(1)} kW`;
        if (s.soc != null) t += ` · ${s.soc} %`;
        acts.push(`<span style="color:${s.bat === "discharge" ? COL.discharge : s.bat === "export" ? COL.export : s.bat === "charge" ? COL.charge : "inherit"}">${esc(t)}</span>`);
      }
      Object.entries(s.ev || {}).filter(([, kw]) => kw > 0.05).forEach(([car, kw]) =>
        acts.push(`<span style="color:${carCol(car)}">${esc(carName(car))} ${esc(L.charges)} · ${kw.toFixed(1)} kW</span>`));
      if (s.heat && L.heat[s.heat]) acts.push(`<span style="opacity:.8">${esc(L.heat[s.heat])}</span>`);
      if (s.sun_w > 50) acts.push(`<span style="color:${COL.sun}">☀ ${(s.sun_w / 1000).toFixed(1)} kW</span>`);
      mid.act.innerHTML = acts.length ? acts.join("<br>") : `<span style="opacity:.55">${esc(L.nothing)}</span>`;
      nowBtn.hidden = i === 0;
      if (fromUser && navigator.vibrate && i % 4 === 0) { try { navigator.vibrate(4); } catch (e) { /* inte alla webbläsare */ } }
    }
    function idxFromPoint(ev) {
      const r = svgEl.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * 400 - C, y = (ev.clientY - r.top) / r.height * 400 - C;
      let a = Math.atan2(y, x) + Math.PI / 2;
      if (a < 0) a += 2 * Math.PI;
      const hours = a / (2 * Math.PI) * 24;                       // klockslag 0-24
      const startH = t0.getHours() + t0.getMinutes() / 60;
      let ahead = hours - startH;
      if (ahead < 0) ahead += 24;
      return Math.round(ahead * 4);
    }
    let dragging = false;
    svgEl.addEventListener("pointerdown", (ev) => { dragging = true; root.classList.add("drag"); svgEl.setPointerCapture(ev.pointerId); show(idxFromPoint(ev), true); ev.preventDefault(); });
    svgEl.addEventListener("pointermove", (ev) => { if (dragging) show(idxFromPoint(ev), true); });
    const stop = () => { dragging = false; root.classList.remove("drag"); };
    svgEl.addEventListener("pointerup", stop);
    svgEl.addEventListener("pointercancel", stop);
    svgEl.addEventListener("keydown", (ev) => {
      const step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 4, PageDown: -4 }[ev.key];
      if (step) { show(idx + step, true); ev.preventDefault(); } else if (ev.key === "Home") { show(0, true); ev.preventDefault(); }
    });
    nowBtn.addEventListener("click", () => show(0, true));
    show(0, false);
    return { show, get index() { return idx; } };
  }
  window.EWPlanClock = { mount };
})();
