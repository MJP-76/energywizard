// EnergyWizard Webdashboard - Fas B: Översikt-sidan med riktig data (portad från
// smartdashboard/app.py:s page_overview()). Resten av sidorna byggs i senare steg.
let PAGES = [];
let currentPage = null;

// Glas + dygnsfärger på som standard - samma designspråk som ewapp (html[data-glass]/
// html[data-ambient][data-tod]), inte en egen plattare stil. localStorage-nycklarna är
// delade namn med ewapp men EGEN lagring (skild origin) - "0" = avstängt av användaren.
(function applyAmbientTheme() {
  const de = document.documentElement;
  const todOf = (h) => (h >= 5 && h < 10 ? "morning" : h >= 10 && h < 16 ? "day" : h >= 16 && h < 21 ? "evening" : "night");
  let glass = "1", amb = "1";
  try { glass = localStorage.getItem("ew_glass") ?? "1"; amb = localStorage.getItem("ew_ambient") ?? "1"; } catch (e) { /* privat läge etc - kör med standard */ }
  if (glass !== "0") de.setAttribute("data-glass", "1"); else de.removeAttribute("data-glass");
  if (amb !== "0") { de.setAttribute("data-ambient", "1"); de.setAttribute("data-tod", todOf(new Date().getHours())); } else { de.removeAttribute("data-ambient"); de.removeAttribute("data-tod"); }
})();

function fmtKrOre(v) {
  if (v == null) return "–";
  return Math.abs(v) < 1 && v !== 0 ? `${Math.round(v * 100)} öre` : `${v.toFixed(2)} kr`;
}
function fmt(v, dec, unit) { return v == null ? "–" : `${v.toFixed(dec)}${unit}`; }

function metricCard(icon, label, value, sub) {
  return `<div class="card"><div class="note">${icon} ${label}</div><h2 style="margin-top:6px">${value}</h2>${sub ? `<div class="note">${sub}</div>` : ""}</div>`;
}

function heatBatteryHtml(hb, compact) {
  if (!hb) return "";
  const icon = hb.status === "Laddar" ? "🔥" : hb.status === "Vilar" ? "💤" : "🧊";
  const cls = hb.status === "Tömmer" ? " tomrer" : "";
  return `
    <div class="heatbatt${compact ? " compact" : ""}${cls}">
      <div class="tank"><div class="fill" style="height:${hb.charge_pct}%"></div></div>
      <div class="info">
        <div><b>${hb.charge_pct.toFixed(0)}%</b> <span class="note">${icon} ${hb.status}</span></div>
        <div class="note">${hb.water_temp.toFixed(0)}°C (${hb.floor.toFixed(0)}–${hb.ceiling.toFixed(0)}°C)</div>
      </div>
    </div>`;
}

// ---------- Besparing (inspirerat av FTW:s savings-kort, egen implementation) ----------
// Samma siffra som den publika sidan: vad tajmningen sparade mot om samma el köpts till
// dygnets snittpris (smartbox/savings.py). Negativa dagar visas som de är.
const SAVINGS_PERIODS = [["today", "Idag"], ["week", "7 dagar"], ["month", "Månad"]];
let savingsPeriod = "week";
try { savingsPeriod = localStorage.getItem("ew_savings_period") || "week"; } catch (e) { /* privat läge */ }


function savingsCardHtml(d) {
  const p = d.periods[savingsPeriod] || d.periods.week;
  const pos = p.saved_kr >= 0;
  const sign = p.saved_kr > 0 ? "+" : p.saved_kr < 0 ? "−" : "";
  const kr = `${sign}${Math.abs(p.saved_kr).toFixed(0)} kr`;
  const pct = p.pct != null ? ` <span style="font-size:1rem;font-weight:700;opacity:.8">(${p.pct > 0 ? "+" : ""}${p.pct.toFixed(0)} %)</span>` : "";
  const sub = p.days
    ? `${p.kwh.toFixed(0)} kWh köpt för ${p.paid_kr.toFixed(0)} kr, mot ${(p.paid_kr + p.saved_kr).toFixed(0)} kr till dygnets snittpris${p.days > 1 ? ` · ${p.days} dagar med data` : ""}`
    : "Ingen mätdata för perioden än.";
  return `
    <div class="card" id="savingscard">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
        <h2 style="margin:0">💰 Sparat genom smart tajmning</h2>
        <div class="seg" id="savingsseg">${SAVINGS_PERIODS.map(([k, l]) => `<button data-p="${k}" class="${k === savingsPeriod ? "on" : ""}">${l}</button>`).join("")}</div>
      </div>
      <div style="font-size:2.1rem;font-weight:800;margin-top:10px;color:${pos ? "var(--acc)" : "var(--bad)"};font-variant-numeric:tabular-nums">${kr}${pct}</div>
      <div class="note">${sub}</div>
      <div id="savingsbars" style="height:90px;margin-top:8px"></div>
    </div>`;
}

function savingsBars(elId, days, height) {
  const el = document.getElementById(elId);
  if (!el || !days || !days.length) return;
  const chart = echarts.init(el, null, { renderer: "svg" });
  const css = getComputedStyle(document.documentElement);
  const good = css.getPropertyValue("--acc").trim() || "#22d3a0", bad = css.getPropertyValue("--bad").trim() || "#f87171";
  chart.setOption({
    grid: { left: height ? 40 : 4, right: 4, top: 6, bottom: height ? 30 : 4 },
    tooltip: { trigger: "axis", formatter: (ps) => `${ps[0].name}: ${ps[0].value >= 0 ? "+" : ""}${ps[0].value.toFixed(2)} kr` },
    xAxis: { type: "category", data: days.map((r) => r.day.slice(5)), show: !!height, axisLabel: { color: "#93a0b8" } },
    yAxis: { type: "value", show: !!height, splitLine: { lineStyle: { color: "rgba(255,255,255,.08)" } }, axisLabel: { color: "#93a0b8" } },
    series: [{ type: "bar", data: days.map((r) => ({ value: r.saved_kr, itemStyle: { color: r.saved_kr >= 0 ? good : bad, borderRadius: r.saved_kr >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3] } })), barMaxWidth: 14 }],
  });
  new ResizeObserver(() => chart.resize()).observe(el);
}

async function mountSavings(slotId) {
  const slot = document.getElementById(slotId);
  if (!slot) return;
  let d;
  try { d = await api("api/savings"); } catch (e) { slot.innerHTML = ""; return; }
  if (!d.ok) { slot.innerHTML = ""; return; }
  const draw = () => {
    slot.innerHTML = savingsCardHtml(d);
    const n = savingsPeriod === "today" ? 1 : savingsPeriod === "week" ? 7 : d.days.filter((r) => r.day.startsWith(d.today.slice(0, 7))).length;
    savingsBars("savingsbars", d.days.slice(-Math.max(n, 7)));
    slot.querySelectorAll("#savingsseg button").forEach((b) => b.onclick = () => {
      savingsPeriod = b.dataset.p;
      try { localStorage.setItem("ew_savings_period", savingsPeriod); } catch (e) { /* privat läge */ }
      draw();
    });
  };
  draw();
  return d;
}

// ---------- Planen framåt i klartext (inspirerat av FTW:s plan brief) ----------
// Beskriver motorns egen plan - elbilens laddpass och värmepumpens grundläge enligt
// elpriset (smartbox/plan_brief.py). Inga nya beslut fattas här.
// Solprognos per dygn (smartbox/solar_days.py): samma timprognos som motorn planerar efter.
function sunDaysHtml(sd) {
  if (!sd || sd.today_kwh == null) return "";
  const f = (v) => v == null ? "–" : (v >= 10 ? v.toFixed(0) : v.toFixed(1).replace(".", ","));
  const tile = (label, v, sub) => `<div class="stat" style="flex:1;min-width:110px;padding:10px 12px">
      <div class="note">${label}</div><div style="font-size:1.25rem;font-weight:700">${f(v)} <span class="note">kWh</span></div>
      ${sub ? `<div class="note">${sub}</div>` : ""}</div>`;
  const today = [sd.today_left_kwh != null ? `${f(sd.today_left_kwh)} kvar` : "", sd.produced_today_kwh != null ? `${f(sd.produced_today_kwh)} hittills` : ""].filter(Boolean).join(" · ");
  return `<div style="margin:0 0 10px"><div class="note" style="margin-bottom:6px">☀️ Solprognos</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">${tile("Idag", sd.today_kwh, today)}${tile("Imorgon", sd.tomorrow_kwh)}${sd.day_after_kwh != null ? tile("I övermorgon", sd.day_after_kwh) : ""}</div></div>`;
}

function planCardHtml(d) {
  const rows = d.items.slice(0, 8).map((i) => `
    <div style="display:flex;gap:12px;padding:9px 0;border-top:1px solid var(--line)${i.active ? ";font-weight:600" : ""}">
      <div style="flex:0 0 158px;white-space:nowrap;font-variant-numeric:tabular-nums">${i.active ? `<span class="badge on" style="margin-right:6px">Nu</span>` : ""}${esc(i.when)}</div>
      <div><div>${esc(i.title)}</div><div class="note">${esc(i.detail)}</div></div>
    </div>`).join("");
  return `
    <div class="card">
      <h2>🗓️ Planen framåt</h2>
      <div style="font-size:1.02rem;margin:4px 0 10px">${esc(d.headline)}</div>
      ${sunDaysHtml(d.solar_days)}
      ${rows || ""}
      ${d.items.length ? `<div class="note" style="margin-top:8px">${esc(d.note)}</div>` : ""}
    </div>`;
}

async function mountPlan(slotId) {
  const slot = document.getElementById(slotId);
  if (!slot) return;
  try {
    const d = await api("api/plan");
    slot.innerHTML = d.ok ? planCardHtml(d) : "";
  } catch (e) { slot.innerHTML = ""; }
}

// ---------- Just nu: levande energiflöde (bara det huset har) ----------
// Huset i mitten, källor till vänster (sol, nät, batteri), förbrukare till höger. Prickarnas fart
// följer effekten, riktningen visar köp/sälj. Inaktivt tonas ned. Klick öppnar enhetens sida.
const FLOW_COL = { sol: "#fbbf24", nat: "#38bdf8", natut: "#22d3a0", batteri: "#0e7490", varmepump: "#fb923c", varmvatten: "#60a5fa", spabad: "#a78bfa", ev: "#22d3a0" };
const reduceMotion = () => { try { return matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } };
let flowTimer = null;

function flowSvg(d) {
  const W = 960, H = 380, hub = { x: 480, y: 190 };
  const nodes = d.nodes.filter((n) => n.key !== "hus"), house = d.nodes.find((n) => n.key === "hus");
  const left = nodes.filter((n) => ["source", "grid", "battery"].includes(n.role)), right = nodes.filter((n) => n.role === "load");
  const place = (arr, x) => arr.map((n, i) => ({ ...n, x, y: arr.length === 1 ? H / 2 : 50 + i * ((H - 100) / (arr.length - 1)) }));
  const all = [...place(left, 110), ...place(right, 850)];
  const col = (n) => n.key === "nat" ? (n.w < -50 ? FLOW_COL.natut : FLOW_COL.nat) : n.key.startsWith("ev_") ? FLOW_COL.ev : (FLOW_COL[n.key] || "#94a3b8");
  const motion = !reduceMotion();
  let paths = "", dots = "", cards = "";
  all.forEach((n, i) => {
    const sx = n.x < hub.x ? n.x + 92 : n.x - 92, ex = n.x < hub.x ? hub.x - 70 : hub.x + 70;
    const id = `fp${i}`, c = col(n);
    // in mot huset: sol, köp från nät, batteri som laddar ur. Ut från huset: förbrukare, sälj, batteri som laddar.
    const inward = n.role === "source" || (n.role === "grid" && n.w > 50) || (n.role === "battery" && n.w < -30);
    const d0 = `M${sx} ${n.y} C${(sx + ex) / 2} ${n.y} ${(sx + ex) / 2} ${hub.y} ${ex} ${hub.y}`;
    paths += `<path id="${id}" d="${d0}" fill="none" stroke="${c}" stroke-width="${n.active ? 2.5 : 1.5}" stroke-dasharray="${n.active ? "0" : "3 6"}" opacity="${n.active ? .55 : .25}"/>`;
    if (n.active && motion && n.w != null) {
      const kw = Math.abs(n.w) / 1000, dur = Math.max(0.7, 3.4 - kw * 0.35).toFixed(2), cnt = kw > 4 ? 4 : kw > 1.5 ? 3 : 2;
      for (let k = 0; k < cnt; k++) {
        const kp = inward === (n.x < hub.x) ? "0;1" : "1;0";
        dots += `<circle r="${(3.5 + Math.min(3, kw / 2)).toFixed(1)}" fill="${c}"><animateMotion dur="${dur}s" begin="${(-k * dur / cnt).toFixed(2)}s" repeatCount="indefinite" keyPoints="${kp}" keyTimes="0;1" calcMode="linear"><mpath href="#${id}"/></animateMotion></circle>`;
      }
    } else if (n.active && motion && n.w == null) {
      dots += `<circle r="5" fill="${c}" opacity=".8"><animateMotion dur="2.4s" repeatCount="indefinite"><mpath href="#${id}"/></animateMotion></circle>`;
    }
    const why = d.why[n.key] || (n.key === "nat" || n.key === "sol" ? "" : "");
    cards += `<g class="fnode${n.active ? " on" : ""}" data-page="${n.page}" transform="translate(${n.x - 90},${n.y - 34})" style="cursor:pointer">
      <rect width="180" height="68" rx="16" fill="var(--card2)" stroke="${n.active ? c : "var(--line)"}" stroke-width="${n.active ? 2 : 1}"/>
      <text x="16" y="28" font-size="20">${esc(n.icon)}</text>
      <text x="46" y="27" font-size="14" font-weight="700" fill="var(--txt)">${esc(n.label)}</text>
      <text x="46" y="47" font-size="12" fill="var(--mut)">${esc(n.detail)}</text>
      ${why ? `<title>${esc(why)}</title>` : ""}
    </g>`;
  });
  const hk = house && house.w != null ? (house.w / 1000).toFixed(1) : "–";
  const hubSvg = `<g class="fnode on" data-page="oversikt" transform="translate(${hub.x - 70},${hub.y - 62})">
      <rect width="140" height="124" rx="28" fill="var(--card2)" stroke="var(--acc)" stroke-width="2"/>
      <path d="M44 56 L70 34 L96 56 V86 H44 Z" fill="none" stroke="var(--acc)" stroke-width="2.5" stroke-linejoin="round"/>
      <text x="70" y="108" text-anchor="middle" font-size="15" font-weight="800" fill="var(--txt)">${hk} kW</text>
    </g>`;
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block" role="img" aria-label="Energiflöde just nu">${paths}${dots}${hubSvg}${cards}</svg>`;
}

async function mountFlow(slotId) {
  const draw = async () => {
    const slot = document.getElementById(slotId);
    if (!slot) { clearInterval(flowTimer); return; }
    let d; try { d = await api("api/flow"); } catch (e) { return; }
    if (!d.ok) { slot.innerHTML = ""; return; }
    const whyRows = d.nodes.filter((n) => d.why[n.key]).map((n) => `<div style="display:flex;gap:10px;align-items:baseline;padding-top:8px;border-top:1px solid var(--line)"><span>${esc(n.icon)}</span><div><b>${esc(n.label)}</b> <span class="note" style="font-size:.9rem">${esc(d.why[n.key])}</span></div></div>`).join("");
    slot.innerHTML = `<div class="card"><div style="display:flex;justify-content:space-between;align-items:baseline"><h2 style="margin:0">⚡ Just nu</h2><span class="note">${esc(d.ts || "")}</span></div>${flowSvg(d)}${whyRows ? `<div style="display:grid;gap:8px;margin-top:6px">${whyRows}</div>` : ""}</div>`;
    slot.querySelectorAll(".fnode[data-page]").forEach((g) => g.addEventListener("click", () => { const pg = g.dataset.page; if (pg && pg !== "oversikt" && PAGES.some((p) => p.id === pg)) openPage(pg); }));
  };
  clearInterval(flowTimer);
  await draw();
  flowTimer = setInterval(() => { if (currentPage === "oversikt") draw(); else clearInterval(flowTimer); }, 15000);
}

// ---------- Dygnet timme för timme: uppmätt bakåt, planerat framåt ----------
function timelineChart(elId, d) {
  const el = document.getElementById(elId);
  if (!el || !d || !d.hours.length) return;
  const chart = echarts.init(el, null, { renderer: "svg" });
  const css = getComputedStyle(document.documentElement), mut = "#93a0b8";
  const labels = d.hours.map((h) => h.slice(11, 13));
  const nowIdx = d.hours.indexOf(d.now);
  const lanes = d.lanes, n = labels.length;
  const laneData = [];
  lanes.forEach((ln, li) => ln.values.forEach((v, i) => { if (v != null && v > 0.02) laneData.push([i, li, v, d.future[i] ? 1 : 0]); }));
  const futArea = nowIdx >= 0 ? [[{ xAxis: labels[nowIdx], itemStyle: { color: "rgba(148,163,184,.08)" } }, { xAxis: labels[n - 1] }]] : [];
  chart.setOption({
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [{ left: 120, right: 52, top: 28, height: "36%" }, { left: 120, right: 52, top: "52%", bottom: 34 }],
    legend: { data: ["Elpris", "Sol"], top: 0, left: 120, textStyle: { color: mut } },
    xAxis: [
      { type: "category", data: labels, gridIndex: 0, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: mut } } },
      { type: "category", data: labels, gridIndex: 1, axisLabel: { color: mut, interval: 2 }, axisLine: { lineStyle: { color: mut } } },
    ],
    yAxis: [
      { type: "value", gridIndex: 0, name: "kr/kWh", nameTextStyle: { color: mut }, axisLabel: { color: mut }, splitLine: { lineStyle: { color: "rgba(148,163,184,.12)" } } },
      { type: "value", gridIndex: 0, name: "kW sol", nameTextStyle: { color: mut }, axisLabel: { color: mut }, splitLine: { show: false } },
      { type: "category", gridIndex: 1, data: lanes.map((l) => l.label), inverse: true, axisLabel: { color: css.getPropertyValue("--txt").trim() || "#fff", fontWeight: 600 }, axisLine: { show: false }, axisTick: { show: false } },
    ],
    tooltip: {
      trigger: "axis",
      formatter: (ps) => {
        const i = ps[0].dataIndex, h = d.hours[i];
        const head = `<b>${h.slice(11, 16)}${d.future[i] ? " · planerat" : ""}</b>`;
        const pr = d.price[i] != null ? `Elpris ${d.price[i].toFixed(2)} kr/kWh` : "";
        const sol = d.solar_kw[i] != null ? `Sol ${d.solar_kw[i].toFixed(1)} kW${d.future[i] ? " (prognos)" : ""}` : "";
        return [head, pr, sol, ...lanes.map((l) => `${esc(l.label)}: ${esc(l.text[i] || "–")}`)].filter(Boolean).join("<br>");
      },
    },
    series: [
      { name: "Sol", type: "bar", color: "#fbbf24", xAxisIndex: 0, yAxisIndex: 1, data: d.solar_kw.map((v, i) => ({ value: v, itemStyle: { color: "#fbbf24", opacity: d.future[i] ? 0.35 : 0.75 } })), barWidth: "70%" },
      { name: "Elpris", type: "line", color: "#38bdf8", step: "middle", xAxisIndex: 0, yAxisIndex: 0, data: d.price, symbol: "none", lineStyle: { color: "#38bdf8", width: 2 },
        markLine: nowIdx >= 0 ? { symbol: "none", label: { formatter: "nu", color: mut, position: "insideStartTop" }, lineStyle: { color: mut, type: "dashed" }, data: [{ xAxis: labels[nowIdx] }] } : undefined,
        markArea: { silent: true, data: futArea } },
      { type: "custom", xAxisIndex: 1, yAxisIndex: 2, data: laneData, renderItem: (params, api) => {
          const i = api.value(0), li = api.value(1), v = api.value(2), fut = api.value(3);
          const p0 = api.coord([i, li]), bw = api.size([1, 0])[0], bh = api.size([0, 1])[1] * 0.62;
          const color = lanes[li].color;
          return { type: "rect", shape: { x: p0[0] - bw / 2 + 1, y: p0[1] - bh / 2, width: bw - 2, height: bh, r: 4 },
                   style: { fill: color, opacity: (fut ? 0.12 : 0.2) + v * (fut ? 0.45 : 0.8), stroke: fut ? color : null, lineDash: fut ? [3, 3] : null, lineWidth: fut ? 1 : 0 } };
        } },
    ],
  });
  new ResizeObserver(() => chart.resize()).observe(el);
}

async function mountTimeline(slotId) {
  const slot = document.getElementById(slotId);
  if (!slot) return;
  let d; try { d = await api("api/timeline"); } catch (e) { slot.innerHTML = ""; return; }
  if (!d.ok) { slot.innerHTML = ""; return; }
  slot.innerHTML = `<div class="card"><h2>🕒 Dygnet timme för timme</h2><div class="note">Till vänster om strecket: det som hände (uppmätt). Till höger: det som är planerat. Starkare färg = mer.</div><div id="timelinechart" style="height:${260 + d.lanes.length * 34}px;margin-top:10px"></div></div>`;
  timelineChart("timelinechart", d);
}

async function renderOversikt() {
  const main = document.getElementById("main");
  main.innerHTML = `<div class="placeholder">Laddar…</div>`;
  const d = await api("api/overview");
  if (!d.ok) {
    // "Ingen data i sensor_log än" = smartbox har inget house_config ännu, oftast en
    // helt ny installation - en bar felrad ger ingen ledtråd om vad man ska göra.
    main.innerHTML = `<div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">👋 Välkommen till EnergyWizard!</div>
      <div class="note" style="margin-top:6px">${d.error || "Ingen data än"} - troligen en ny installation. Gå till
        <b>Inställningar</b> och kör entitetsväljaren för att hitta din värmepump, bilar, solceller m.m. i Home
        Assistant. Kryssa i det du har och tryck <b>Spara och starta</b> (eller ladda ner filen som din
        <code>house_config.yaml</code> och starta om smartbox, om du skrivit din config själv).</div>
      <button class="icobtn" id="gotosettings" style="margin-top:10px">Gå till Inställningar</button>
    </div>`;
    document.getElementById("gotosettings").onclick = () => openPage("installningar");
    return;
  }
  const emoji = d.mode === "CHEAP" ? "🟢" : d.mode === "EXPENSIVE" ? "🔴" : "⏸️";
  const netLabel = d.net_power_w != null && d.net_power_w < 0 ? "☀️ Netto (Säljer!)" : "🔌 Netto (Köper)";
  const tariff = d.is_high_load ? "🔴 Höglast" : "🟢 Baslast";
  main.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.15rem;font-weight:700">${emoji} ${d.decision}</div>
      <div class="note" style="margin-top:4px">💸 ${fmtKrOre(d.price)}/kWh · 🌡️ Inne ${fmt(d.indoor_temp, 1, "°C")} (mål ${d.indoor_target.toFixed(0)}) · 🌳 Ute ${fmt(d.outdoor_temp, 1, "°C")}</div>
    </div>
    <div id="flowslot" style="margin-bottom:16px"></div>
    <div class="grid" style="margin-bottom:16px"><div id="savingsslot"></div><div id="planslot"></div></div>
    <div class="card" style="margin-bottom:16px"><span class="note">⚡ Aktuell effekttariff: ${tariff}</span></div>
    <div class="grid" style="margin-bottom:16px">
      ${metricCard("⚡", "Elpris just nu", fmtKrOre(d.price) + "/kWh")}
      ${metricCard("🌡️", "Inne", fmt(d.indoor_temp, 1, "°C"), `Mål ${d.indoor_target.toFixed(0)}°C${d.indoor_humidity != null ? " · 💧 " + d.indoor_humidity.toFixed(0) + "%" : ""}`)}
      ${metricCard("🌲", "Ute (Pump)", fmt(d.outdoor_temp, 1, "°C"))}
      ${metricCard(d.net_power_w < 0 ? "☀️" : "🔌", d.net_power_w < 0 ? "Netto (Säljer!)" : "Netto (Köper)", d.net_power_w != null ? (d.net_power_w / 1000).toFixed(2) + " kW" : "–")}
      ${metricCard("☀️", "PV-effekt", d.pv_power_w != null ? (d.pv_power_w / 1000).toFixed(2) + " kW" : "–")}
      ${metricCard("🛁", "Varmvatten", fmt(d.water_temp, 1, "°C"))}
      ${metricCard("🚗", "EV Laddning", d.ev_power_kw != null ? d.ev_power_kw.toFixed(1) + " kW" : "–")}
      <div class="card"><div class="note">🔋 Värmebatteri</div><div style="margin-top:8px">${heatBatteryHtml(d.heat_battery, true)}</div></div>
    </div>
    <div id="timelineslot"></div>
    <div class="note" style="margin-top:10px">Senast mätt: ${d.sthlm_time}</div>`;
  mountFlow("flowslot");
  mountSavings("savingsslot");
  mountPlan("planslot");
  mountTimeline("timelineslot");
}

function badge(cls, text) { return `<span class="badge ${cls}">${text}</span>`; }

function statTile(label, value, sub) {
  return `<div class="stat"><div class="v">${value}</div><div class="l">${label}</div>${sub ? `<div class="l">${sub}</div>` : ""}</div>`;
}

function barRow(name, pct, valueLabel) {
  const p = pct == null ? 0 : Math.max(0, Math.min(100, pct));
  return `<div class="barrow"><div class="name">${name}</div><div class="track"><div class="fill" style="width:${p}%"></div></div><div class="val">${valueLabel}</div></div>`;
}

function lineChart(elId, series, opts) {
  const el = document.getElementById(elId);
  if (!el || !series.length) return;
  const chart = echarts.init(el, null, { renderer: "svg" });
  chart.setOption({
    grid: { left: 46, right: 16, top: 16, bottom: 36 },
    xAxis: { type: "category", data: series.map(p => p.t.slice(11, 16)), axisLabel: { interval: Math.ceil(series.length / 8) }, axisLine: { lineStyle: { color: "#93a0b8" } } },
    yAxis: { type: "value", axisLine: { lineStyle: { color: "#93a0b8" } }, splitLine: { lineStyle: { color: "rgba(255,255,255,.08)" } }, ...(opts && opts.yAxis) || {} },
    series: [{ type: "line", data: series.map(p => p[opts && opts.yKey || "p"]), step: opts && opts.step, lineStyle: { color: (opts && opts.color) || "#38bdf8", width: 2 }, areaStyle: { color: (opts && opts.areaColor) || "rgba(56,189,248,.15)" }, symbol: "none" }],
  });
  new ResizeObserver(() => chart.resize()).observe(el);
}

async function loadPage(path, build) {
  const main = document.getElementById("main");
  main.innerHTML = `<div class="placeholder">Laddar…</div>`;
  let d;
  try { d = await api(path); } catch (e) { main.innerHTML = `<div class="placeholder">${e.message}</div>`; return; }
  if (!d.ok) { main.innerHTML = `<div class="placeholder">${d.error || "Kunde inte läsa data"}</div>`; return; }
  main.innerHTML = build(d);
  return d;
}

function evPlanChart(elId, d) {
  const el = document.getElementById(elId);
  if (!el) return;
  const mut = "#93a0b8", colors = { tesla: "#22d3a0", nissan: "#38bdf8" };
  const times = [...new Set([...d.plan.map((p) => p.t.slice(0, 16)), ...d.plan_prices.map((p) => p.t.slice(0, 16))])].sort();
  const first = d.plan[0].t.slice(0, 16), last = d.plan[d.plan.length - 1].t.slice(0, 16);
  const ts = times.filter((t) => t >= first.slice(0, 13) && t <= last);       // planens första timme -> sista slotten
  const cars = [...new Set(d.plan.map((p) => p.car))];
  const byKey = {}; d.plan.forEach((p) => { byKey[p.car + p.t.slice(0, 16)] = p; });
  const priceAt = (t) => { let v = null; d.plan_prices.forEach((p) => { if (p.t.slice(0, 16) <= t) v = p.p; }); return v; };
  const chart = echarts.init(el, null, { renderer: "svg" });
  chart.setOption({
    grid: { left: 46, right: 56, top: 30, bottom: 30 }, legend: { top: 0, textStyle: { color: mut } },
    tooltip: { trigger: "axis", formatter: (ps) => { const t = ts[ps[0].dataIndex];
      return [`<b>${t.slice(5, 10).replace("-", "/")} ${t.slice(11, 16)}</b>`, ...cars.map((c) => { const p = byKey[c + t]; return p ? `${c[0].toUpperCase() + c.slice(1)}: ${p.kw.toFixed(1)} kW${p.soc0 != null ? ` · ${Math.round(p.soc0)} → ${Math.round(p.soc1)} %` : ""}` : null; }).filter(Boolean),
        priceAt(t) != null ? `Elpris ${priceAt(t).toFixed(2)} kr/kWh` : ""].filter(Boolean).join("<br>"); } },
    xAxis: { type: "category", data: ts.map((t) => t.slice(11, 16)), axisLabel: { color: mut, interval: (i) => ts[i].slice(14, 16) === "00" && Number(ts[i].slice(11, 13)) % 2 === 0 } },
    yAxis: [{ type: "value", name: "kW", nameTextStyle: { color: mut }, axisLabel: { color: mut }, splitLine: { lineStyle: { color: "rgba(148,163,184,.12)" } } },
            { type: "value", name: "kr/kWh", nameTextStyle: { color: mut }, axisLabel: { color: mut }, splitLine: { show: false } }],
    series: [...cars.map((c) => ({ name: c[0].toUpperCase() + c.slice(1), type: "bar", stack: "ev", color: colors[c] || "#a78bfa", data: ts.map((t) => (byKey[c + t] ? byKey[c + t].kw : 0)), itemStyle: { color: colors[c] || "#a78bfa", borderRadius: 2 } })),
             { name: "Elpris", type: "line", color: "#fbbf24", step: "end", yAxisIndex: 1, data: ts.map(priceAt), symbol: "none", lineStyle: { color: "#fbbf24", width: 2 } }],
  });
  new ResizeObserver(() => chart.resize()).observe(el);
}

async function renderElbil() {
  const d = await loadPage("api/car", (d) => `
    <div class="grid" style="margin-bottom:16px">
      ${d.cars.map(c => {
        const s = d.schedule_today.find(s => s.car_id === c.id) || { target_time: "07:00", target_soc: 100, enabled: false };
        return `<div class="card">
        <div style="font-size:1.05rem;font-weight:700">🚗 ${c.name}</div>
        <div class="v" style="margin:10px 0 2px;font-size:1.6rem">${fmt(c.soc, 0, "%")}</div>
        <div class="note">${c.stale ? badge("warn", "⚠️ gammalt värde") : badge("on", "live")} ${c.status ? "· " + c.status : ""}</div>
        <div class="note" style="margin-top:6px">⚡ ${fmt(c.power_kw, 1, " kW")} just nu${c.planned_kwh_today != null ? ` · 📅 ${c.planned_kwh_today.toFixed(1)} kWh planerat idag` : ""}</div>
        ${c.climate_state ? `<div class="note">🌡️ Klimat: ${c.climate_state}${c.climate_temp != null ? " (" + c.climate_temp.toFixed(0) + "°C)" : ""}</div>` : ""}
        <div class="seg" style="margin-top:12px;flex-wrap:wrap">
          <button data-car="${c.id}" data-kind="start">Ladda nu</button>
          <button data-car="${c.id}" data-kind="max">Max</button>
          <button data-car="${c.id}" data-kind="stop">Stoppa</button>
          <button data-car="${c.id}" data-kind="auto">Auto</button>
        </div>
        <div class="seg" style="margin-top:6px">
          <button data-car="${c.id}" data-kind="heat_on">🔥 Värm</button>
          <button data-car="${c.id}" data-kind="heat_off">Stoppa värme</button>
        </div>
        <div class="card" style="margin-top:12px;padding:12px">
          <div class="note">📅 Dagens schema</div>
          <div class="numfield" style="margin-top:6px">
            <input type="time" class="sch-time" data-car="${c.id}" value="${s.target_time || "07:00"}">
            <input type="number" class="sch-soc" data-car="${c.id}" min="20" max="100" value="${s.target_soc || 100}"> %
          </div>
          <div class="togglerow"><span>Aktivt idag</span><label class="switch"><input type="checkbox" class="sch-enabled" data-car="${c.id}" ${s.enabled ? "checked" : ""}><span class="slider"></span></label></div>
          <button class="icobtn sch-save" data-car="${c.id}" style="margin-top:6px">Spara schema</button>
        </div>
      </div>`;
      }).join("")}
    </div>
    <div class="card" style="margin-bottom:16px"><h2>🔌 Laddplanen</h2><div class="note">Planerad laddeffekt per kvart mot elpriset. Håll muspekaren över en stapel för batterinivån.</div>${d.plan && d.plan.length ? `<div id="evplanchart" style="height:260px;margin-top:10px"></div>` : `<div class="note" style="margin-top:8px">Ingen laddning planerad just nu.</div>`}</div>
    <div class="note">Laddström: ${fmt(d.current_a, 0, " A")} · Dynamisk gräns: ${fmt(d.dynamic_limit_a, 0, " A")} · Målgräns just nu: ${fmt(d.current_target_limit, 0, " A")}</div>
    <div id="tesla-access" style="margin-top:16px"></div>`);
  if (!d) return;
  if (d.plan && d.plan.length) evPlanChart("evplanchart", d);
  document.querySelectorAll("[data-kind]").forEach(b => b.onclick = () => postAction(`api/car/${b.dataset.car}/action`, { kind: b.dataset.kind }).then(renderElbil));
  loadTeslaAccess();
  document.querySelectorAll(".sch-save").forEach(b => b.onclick = () => {
    const car = b.dataset.car;
    const time = document.querySelector(`.sch-time[data-car="${car}"]`).value;
    const soc = parseInt(document.querySelector(`.sch-soc[data-car="${car}"]`).value, 10);
    const enabled = document.querySelector(`.sch-enabled[data-car="${car}"]`).checked;
    postAction("api/schedule", { car, day: new Date().getDay() === 0 ? 6 : new Date().getDay() - 1, time, soc, enabled }, "Schema sparat").then(renderElbil);
  });
}

// Lås/luckor - eget omverifieringssteg (samma princip som ewapp: lösenordet igen, 10 min)
// innan själva kommandot går igenom. Se webdashboard/app.py:s /api/secure + /api/tesla/access.
async function loadTeslaAccess() {
  const box = document.getElementById("tesla-access");
  if (!box) return;
  let d;
  try { d = await api("api/tesla/access-state"); } catch { return; }
  const a = d.access;
  if (!a) return;
  box.innerHTML = `<div class="card">
    <div style="font-size:1.05rem;font-weight:700">🔒 Tesla – lås &amp; luckor</div>
    <div class="note" style="margin-top:4px">Bilen är ${a.locked ? "<b>låst</b>" : "<b style='color:var(--warn,#e8973a)'>upplåst</b>"}. Upplåsning och luckor kräver lösenordet igen (gäller i 10 min).</div>
    <div class="seg" style="margin-top:10px;flex-wrap:wrap">
      <button data-access="${a.locked ? "unlock" : "lock"}">${a.locked ? "Lås upp" : "Lås"}</button>
      <button data-access="trunk">${a.trunk ? "Stäng baklucka" : "Öppna baklucka"}</button>
      <button data-access="frunk">${a.frunk ? "Stäng framlucka" : "Öppna framlucka"}</button>
    </div>
  </div>`;
  box.querySelectorAll("[data-access]").forEach(b => b.onclick = () => teslaAccess(b.dataset.access));
}

async function teslaAccess(what) {
  try {
    const d = await api("api/tesla/access", { method: "POST", body: JSON.stringify({ what }) });
    toast(d.msg || "Klart");
    loadTeslaAccess();
  } catch (e) {
    if (e.message !== "secure") { toast("⚠️ " + e.message); return; }
    const pw = prompt("För din säkerhet krävs lösenordet igen för att låsa upp bilen eller öppna luckor:");
    if (!pw) return;
    try {
      await api("api/secure", { method: "POST", body: JSON.stringify({ password: pw }) });
    } catch (e2) { toast("⚠️ " + e2.message); return; }
    teslaAccess(what);
  }
}

async function renderSolceller() {
  const d = await loadPage("api/solar", (d) => `
    <div class="grid" style="margin-bottom:16px">
      ${statTile("☀️ PV-effekt", fmt(d.pv_power_w != null ? d.pv_power_w / 1000 : null, 2, " kW"))}
      ${statTile("🔆 Idag", fmt(d.solar_today_kwh, 1, " kWh"))}
      ${statTile("📈 Prognos nu", fmt(d.solar_forecast_w != null ? d.solar_forecast_w / 1000 : null, 2, " kW"))}
      ${statTile("🚫 Exportgräns", d.solar_limit_pct != null ? d.solar_limit_pct.toFixed(0) + " %" : "Ingen", d.solar_limit_pct != null && d.solar_limit_pct < 100 ? "AI begränsar (minuspris)" : "")}
    </div>
    ${d.battery_soc != null ? `<div class="card" style="margin-bottom:16px">
      <h2>🔋 Husbatteri</h2>
      ${barRow("Laddning", d.battery_soc, d.battery_soc.toFixed(0) + "%")}
      <div class="note" style="margin-top:6px">${fmt(d.battery_power_w, 0, " W")} ${d.battery_power_w > 0 ? "(laddar)" : d.battery_power_w < 0 ? "(laddar ur)" : ""}</div>
    </div>` : ""}
    <div class="card${d.ai_limit ? " row-disabled" : ""}" style="margin-bottom:16px">
      <h2>🚫 Manuell exportgräns${d.ai_limit ? " · AI:n styr just nu (minuspris) – manuell ändring spärrad" : ""}</h2>
      <div class="numfield" style="margin-top:8px"><input type="range" id="solarlimit" min="0" max="100" step="5" value="${d.solar_limit_pct != null ? d.solar_limit_pct : 100}"><span id="solarlimitval" style="min-width:48px;text-align:right;font-weight:700">${d.solar_limit_pct != null ? d.solar_limit_pct.toFixed(0) : 100} %</span></div>
      <button class="icobtn" id="setsolarlimitbtn" style="margin-top:10px">Sätt gräns</button>
      <div class="note" style="margin-top:12px">Begränsa export automatiskt när priset går under:</div>
      <div class="numfield" style="margin-top:6px"><input type="number" id="solarfloor" step="0.1" min="-1" max="5" value="${d.export_price_floor}"> kr/kWh <button class="icobtn" id="setsolarfloorbtn">Spara</button></div>
      <div class="togglerow" style="margin-top:6px"><span>Avisera vid begränsning</span><label class="switch"><input type="checkbox" id="solarnotify" ${d.notify ? "checked" : ""}><span class="slider"></span></label></div>
    </div>
    <div class="card"><h2>Elpris</h2><div class="note">Styr när exportbegränsningen slår till (minuspris)</div><div id="solarpricechart" style="height:220px;margin-top:10px"></div></div>`);
  if (d && d.price_24h) lineChart("solarpricechart", d.price_24h, { step: "end" });
  if (d) {
    const rangeEl = document.getElementById("solarlimit"), valEl = document.getElementById("solarlimitval");
    rangeEl.oninput = () => valEl.textContent = rangeEl.value + " %";
    document.getElementById("setsolarlimitbtn").onclick = () => postAction("api/energy-action/limit", { value: parseInt(rangeEl.value, 10) }).then(renderSolceller);
    document.getElementById("setsolarfloorbtn").onclick = () => postAction("api/energy-action/floor", { value: parseFloat(document.getElementById("solarfloor").value) }).then(renderSolceller);
    document.getElementById("solarnotify").onchange = (e) => postAction("api/energy-action/notify", { value: e.target.checked });
  }
}

async function renderEkonomi() {
  const d = await loadPage("api/economy", (d) => `
    <div class="grid" style="margin-bottom:16px">
      ${statTile("💸 Elpris just nu", fmtKrOre(d.price) + "/kWh")}
      ${statTile("📉 Lägst idag", fmtKrOre(d.price_min) + "/kWh")}
      ${statTile("📊 Snitt idag", fmtKrOre(d.price_avg) + "/kWh")}
      ${statTile("📈 Högst idag", fmtKrOre(d.price_max) + "/kWh")}
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>💰 Uppskattad kostnad idag</h2>
      <div class="v" style="font-size:1.8rem">${d.est_cost_today != null ? d.est_cost_today.toFixed(2) + " kr" : "–"}</div>
      <div class="note" style="margin-top:4px">${fmt(d.accumulated_consumption_kwh, 1, " kWh")} förbrukat × dagens snittpris - en grov uppskattning, inte en exakt timme-för-timme-kostnad.</div>
    </div>
    <div class="card" style="margin-bottom:16px"><h2>📊 Sparat per dag</h2><div class="note">Grönt = billigare än dygnets snittpris, rött = dyrare. Senaste 31 dagarna.</div><div id="econsavingsbars" style="height:220px;margin-top:10px"></div></div>
    <div class="card"><h2>Elpris senaste dygnet</h2><div id="econpricechart" style="height:240px;margin-top:10px"></div></div>`);
  if (d && d.price_24h) lineChart("econpricechart", d.price_24h, { step: "end" });
  if (d) api("api/savings").then((sv) => { if (sv.ok) savingsBars("econsavingsbars", sv.days, 220); }).catch(() => {});
}

async function renderElforbrukning() {
  const d = await loadPage("api/consumption", (d) => {
    const b = d.breakdown;
    const maxW = b ? Math.max(b.total_w || 0, 1) : 1;
    return `
    <div class="grid" style="margin-bottom:16px">
      ${statTile("⚡ Just nu", fmt(d.avg_w_tot != null ? d.avg_w_tot / 1000 : null, 2, " kW"))}
      ${statTile("🏠 Hus (bas)", fmt(d.house_consumption_w != null ? d.house_consumption_w / 1000 : null, 2, " kW"))}
      ${statTile("📐 Prognos baslast", fmt(d.predicted_base_load_kw, 2, " kW"))}
      ${statTile("🛡️ Effektvakt", d.peak_shaving_active ? badge("warn", "griper in") : badge("on", "normal läge"))}
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>🔌 Faser</h2>
      ${barRow("L1", d.avg_w_l1 != null ? d.avg_w_l1 / maxW * 100 : 0, fmt(d.avg_w_l1, 0, " W"))}
      ${barRow("L2", d.avg_w_l2 != null ? d.avg_w_l2 / maxW * 100 : 0, fmt(d.avg_w_l2, 0, " W"))}
      ${barRow("L3", d.avg_w_l3 != null ? d.avg_w_l3 / maxW * 100 : 0, fmt(d.avg_w_l3, 0, " W"))}
    </div>
    ${b ? `<div class="card">
      <h2>📦 Vad drar strömmen</h2>
      ${barRow("🚗 Elbil", b.ev_w / maxW * 100, fmt(b.ev_w, 0, " W"))}
      ${barRow("♨️ Värmepump", b.pump_w / maxW * 100, fmt(b.pump_w, 0, " W"))}
      ${barRow("🛁 Spabad", b.spa_w / maxW * 100, fmt(b.spa_w, 0, " W"))}
      ${barRow("❓ Oförklarat", b.unexplained_w / maxW * 100, fmt(b.unexplained_w, 0, " W"))}
      ${barRow("Σ Totalt", 100, fmt(b.total_w, 0, " W"))}
    </div>` : `<div class="note">Ingen uppdelning loggad än.</div>`}
    <div class="card" style="margin-top:16px">
      <h2>🛡️ Effektvakt (peak shaving)</h2>
      <div class="togglerow"><span>Effektvakt på</span><label class="switch"><input type="checkbox" id="peakenabled" ${d.peak_shaving_enabled ? "checked" : ""}><span class="slider"></span></label></div>
      <div class="numfield${d.peak_shaving_enabled ? "" : " row-disabled"}" style="margin-top:8px" id="peaklimitrow">Gräns: <input type="number" id="peaklimit" step="0.5" min="1" value="${d.power_limit_kw != null ? d.power_limit_kw : ""}"> kW <button class="icobtn" id="peaklimitbtn">Spara</button></div>
    </div>`;
  });
  if (d) {
    document.getElementById("peakenabled").onchange = (e) => postAction("api/settings-action", { key: "peak_shaving_enabled", value: e.target.checked }).then(renderElforbrukning);
    const btn = document.getElementById("peaklimitbtn");
    if (btn) btn.onclick = () => postAction("api/settings-action", { key: "power_limit_kw", value: parseFloat(document.getElementById("peaklimit").value) }).then(renderElforbrukning);
  }
}

async function renderSpabad() {
  const d = await loadPage("api/spa", (d) => `
    <div class="grid" style="margin-bottom:16px">
      ${statTile("🛁 Temperatur", fmt(d.temp, 1, "°C"))}
      ${statTile("🎯 Mål", fmt(d.target, 1, "°C"))}
      ${statTile("🔥 Värmare", d.heater_running ? badge("on", "värmer") : badge("off", "av"))}
      ${statTile("⚡ Effekt", fmt(d.power_w, 0, " W"))}
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>🎛️ Styrning</h2>
      <div class="togglerow"><span>Tvångsvärme (värm nu, oavsett pris)</span><label class="switch"><input type="checkbox" id="spaforce" ${d.force_heat ? "checked" : ""}><span class="slider"></span></label></div>
      <div class="togglerow"><span>Eco-läge (håll nere temperaturen)</span><label class="switch"><input type="checkbox" id="spaeco" ${d.eco ? "checked" : ""}><span class="slider"></span></label></div>
      <button class="icobtn" id="spaautobtn" style="margin-top:10px">Auto (följ schemat)</button>
    </div>
    <div class="grid" style="margin-bottom:16px">
      <div class="card">
        <h2>🌡️ Temperaturer</h2>
        <div class="note">Som värmepumpens: vad motorn håller badet på i de olika lägena.</div>
        <div class="numfield" style="margin-top:10px;flex-wrap:wrap;gap:10px">
          <label>Normal <input type="number" id="spanormal" step="0.5" min="20" max="40" value="${d.normal_temp ?? ""}"> °C</label>
          <label>Max (minuspris/sol) <input type="number" id="spamax" step="0.5" min="30" max="40" value="${d.max_temp ?? ""}"> °C</label>
          <label>Eco-golv <input type="number" id="spalow" step="0.5" min="10" max="30" value="${d.low_temp ?? ""}"> °C</label>
        </div>
        <div class="note" style="margin-top:6px">Max är aldrig över 40 °C - motorns säkerhetsgräns.</div>
        <button class="icobtn" id="spatempsave" style="margin-top:10px">Spara temperaturer</button>
      </div>
      <div class="card">
        <h2>⏰ Klart till</h2>
        <div class="note">${d.ready_enabled && d.ready_at ? `Aktivt: ${d.ready_at.replace("T", " ")} · ${fmt(d.ready_temp, 1, "°C")}. Motorn värmer på de billigaste timmarna fram till dess.` : "Av - badet följer sitt vanliga läge."}</div>
        <div class="numfield" style="margin-top:10px;flex-wrap:wrap;gap:10px">
          <input type="datetime-local" id="spareadyat" value="${d.ready_at || ""}">
          <input type="number" id="spareadytemp" step="0.5" min="20" max="40" value="${d.ready_temp ?? 38}"> °C
        </div>
        <div style="display:flex;gap:8px;margin-top:10px"><button class="icobtn" id="spareadysave">Spara</button>${d.ready_enabled ? `<button class="icobtn" id="spareadyoff">Stäng av</button>` : ""}</div>
      </div>
    </div>
    <div class="card" style="margin-bottom:16px"><h2>📈 Senaste dygnet</h2><div class="note">Temperatur mot mål. Skuggat = värmaren gick.</div><div id="spachart" style="height:240px;margin-top:10px"></div></div>
    <div class="card"><h2>📡 Trådlös anslutning</h2><div class="note">Signal: ${fmt(d.signal_pct, 0, "%")} · Kanal: ${d.rf_channel != null ? d.rf_channel : "–"}</div></div>`);
  if (d) {
    document.getElementById("spatempsave").onclick = async () => {
      for (const [id, key] of [["spanormal", "spa_normal_temp"], ["spamax", "spa_max_temp"], ["spalow", "spa_low_temp"]]) {
        const v = parseFloat(document.getElementById(id).value);
        if (!isNaN(v)) await postAction("api/settings-action", { key, value: v });
      }
      renderSpabad();
    };
    document.getElementById("spareadysave").onclick = () => {
      const when = document.getElementById("spareadyat").value;
      if (!when) return;
      postAction("api/home-action/spa_ready", { when, temp: parseFloat(document.getElementById("spareadytemp").value) }).then(renderSpabad);
    };
    const off = document.getElementById("spareadyoff");
    if (off) off.onclick = () => postAction("api/home-action/spa_ready", { off: true }).then(renderSpabad);
    if (d.history && d.history.length) {
      const el = document.getElementById("spachart"), chart = echarts.init(el, null, { renderer: "svg" }), mut = "#93a0b8";
      chart.setOption({
        grid: { left: 46, right: 16, top: 24, bottom: 30 }, legend: { top: 0, textStyle: { color: mut } }, tooltip: { trigger: "axis" },
        xAxis: { type: "category", data: d.history.map((h) => h.t.slice(11, 16)), axisLabel: { color: mut, interval: 2 } },
        yAxis: { type: "value", scale: true, name: "°C", axisLabel: { color: mut }, splitLine: { lineStyle: { color: "rgba(148,163,184,.12)" } } },
        series: [
          { name: "Temperatur", type: "line", color: "#a78bfa", data: d.history.map((h) => h.temp), symbol: "none", smooth: true, lineStyle: { color: "#a78bfa", width: 2.5 },
            markArea: { silent: true, itemStyle: { color: "rgba(167,139,250,.12)" }, data: d.history.map((h, i) => h.heating > 0.2 ? [{ xAxis: i }, { xAxis: Math.min(i + 1, d.history.length - 1) }] : null).filter(Boolean) } },
          { name: "Mål", type: "line", color: "#93a0b8", step: "middle", data: d.history.map((h) => h.target), symbol: "none", lineStyle: { color: mut, type: "dashed" } },
        ],
      });
      new ResizeObserver(() => chart.resize()).observe(el);
    }
    document.getElementById("spaforce").onchange = (e) => postAction("api/home-action/spa_heat", { value: e.target.checked });
    document.getElementById("spaeco").onchange = (e) => postAction("api/home-action/spa_eco", { value: e.target.checked });
    document.getElementById("spaautobtn").onclick = () => postAction("api/home-action/spa_auto", {}).then(renderSpabad);
  }
}

async function renderTemperaturer() {
  await loadPage("api/temperatures", (d) => `
    <div class="grid" style="margin-bottom:16px">
      ${statTile("🏠 Inne", fmt(d.indoor_temp, 1, "°C"), d.indoor_humidity != null ? "💧 " + d.indoor_humidity.toFixed(0) + "%" : "")}
      ${statTile("🌳 Ute", fmt(d.outdoor_temp, 1, "°C"))}
      ${statTile("🌬️ Ventilation in", fmt(d.vent_supply_temp, 1, "°C"))}
      ${statTile("🌬️ Ventilation ut", fmt(d.vent_exhaust_temp, 1, "°C"))}
    </div>
    <div class="card"><h2>🌡️ Rum</h2>
      ${d.rooms.length ? d.rooms.map(r => barRow(r.name, (r.temp + 10) * 3, r.temp.toFixed(1) + "°C")).join("") : `<div class="note">Inga rumsgivare hittade.</div>`}
    </div>`);
}

async function renderPrognos() {
  const d = await loadPage("api/forecast", (d) => `
    <div class="card" style="margin-bottom:16px"><h2>📅 Elpris kommande timmar</h2><div id="forecastpricechart" style="height:220px;margin-top:10px"></div></div>
    <div class="card"><h2>🌤️ Väderprognos</h2><div id="forecastweatherchart" style="height:220px;margin-top:10px"></div>
      <div class="note" style="margin-top:8px">Regnrisk/åskrisk anges i procent, molnighet i procent av himlen.</div></div>`);
  if (d) {
    if (d.prices.length) lineChart("forecastpricechart", d.prices, { step: "end" });
    if (d.weather.length) lineChart("forecastweatherchart", d.weather, { yKey: "temp", color: "#fbbf24", areaColor: "rgba(251,191,36,.15)" });
  }
}

// ---------- Historik (inspirerat av FTW:s History-vy, egen implementation) ----------
// Summor Idag/7 dagar/30 dagar + effekt över tid + senaste värden (smartbox/energy_history.py).
let histPeriod = "today", histRange = "24h";
try { histPeriod = localStorage.getItem("ew_hist_period") || "today"; histRange = localStorage.getItem("ew_hist_range") || "24h"; } catch (e) { /* privat läge */ }
const HIST_COL = { grid: "#e11d74", solar: "#b38b00", battery: "#0e7490", house: "#64748b" };

function kwhTile(label, v, sub, color) {
  return `<div class="stat" style="border-left-color:${color}"><div class="l" style="text-transform:none;font-size:.85rem">${label}</div><div class="v">${v != null ? (v >= 100 ? v.toFixed(0) : v.toFixed(1)) : "–"} <span style="font-size:.9rem;font-weight:600;color:var(--mut)">kWh</span></div><div class="l" style="text-transform:none">${sub}</div></div>`;
}
function fmtW(w) { return w == null ? "–" : Math.abs(w) >= 1000 ? `${(w / 1000).toFixed(1)} kW` : `${Math.round(w)} W`; }

function historyHtml(d) {
  const t = d.totals[histPeriod];
  const seg = (id, cur, opts) => `<div class="seg" id="${id}">${opts.map(([k, l]) => `<button data-v="${k}" class="${k === cur ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const tiles = t ? [
    kwhTile("Förbrukat hemma", t.used_kwh, "allt huset drog", HIST_COL.house),
    t.solar_kwh != null ? kwhTile("Solel", t.solar_kwh, "vad panelerna gav", HIST_COL.solar) : "",
    kwhTile("Köpt", t.bought_kwh, "från elnätet", HIST_COL.grid),
    kwhTile("Sålt", t.sold_kwh, "ut på elnätet", HIST_COL.grid),
    t.battery_in_kwh != null ? kwhTile("Batteri", t.battery_in_kwh, `in · ${t.battery_out_kwh.toFixed(1)} kWh ut`, HIST_COL.battery) : "",
  ].join("") : `<div class="note">Ingen mätdata för perioden än.</div>`;
  const L = d.latest || {};
  const latest = [["Nät", HIST_COL.grid, L.grid_w == null ? "–" : fmtW(Math.abs(L.grid_w)), L.grid_w == null ? "" : L.grid_w < -50 ? "säljer" : "köper"],
    ["Sol", HIST_COL.solar, fmtW(L.solar_w), "producerar"],
    ...(L.battery_w != null ? [["Batteri", HIST_COL.battery, fmtW(Math.abs(L.battery_w)), Math.abs(L.battery_w) < 30 ? "vilar" : L.battery_w > 0 ? "laddar" : "laddar ur"]] : []),
    ["Hus", HIST_COL.house, fmtW(L.house_w), "använder"]]
    .map(([n, c, v, s]) => `<div style="border-left:3px solid ${c};padding-left:10px"><div class="note" style="text-transform:uppercase;letter-spacing:.04em;font-size:.72rem">${n}</div><div style="font-size:1.25rem;font-weight:800">${v}</div><div class="note" style="font-size:.72rem;text-transform:uppercase">${s}</div></div>`).join("");
  return `
    <div class="card" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><h2 style="margin:0">⚡ Energi</h2>${seg("histperiod", histPeriod, [["today", "Idag"], ["7d", "7 dagar"], ["30d", "30 dagar"]])}</div>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-top:12px">${tiles}</div>
      ${t && t.summary ? `<div class="note" style="margin-top:10px">${esc(t.summary)}</div>` : ""}
    </div>
    <div class="card" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><h2 style="margin:0">📈 Effekt över tid</h2>${seg("histrange", histRange, [["24h", "24 h"], ["7d", "7 d"], ["30d", "30 d"], ["1y", "1 år"]])}</div>
      <div id="histchart" style="height:300px;margin-top:10px"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:12px;margin-top:12px">${latest}</div>
      <div class="note" style="margin-top:8px">Uppåt = in i huset (köpt), nedåt = ut (sålt, solproduktion). Senast mätt ${L.ts ? new Date(L.ts).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" }) : "–"}.</div>
    </div>`;
}

function historyChart(sr) {
  const el = document.getElementById("histchart");
  if (!el || !sr || !sr.t.length) return;
  const chart = echarts.init(el, null, { renderer: "svg" });
  const fmtT = sr.range === "24h" ? (x) => x.slice(11, 16) : sr.range === "1y" ? (x) => x.slice(5, 10) : (x) => `${x.slice(8, 10)}/${x.slice(5, 7)} ${x.slice(11, 13)}`;
  const line = (name, data, color) => ({ name, type: "line", data, symbol: "none", connectNulls: false, lineStyle: { width: 2, color }, itemStyle: { color } });
  const series = [line("Nät", sr.grid_kw, HIST_COL.grid),
    line("Sol", sr.solar_kw.map((v) => (v == null ? null : -v)), HIST_COL.solar),
    line("Hus", sr.house_kw, HIST_COL.house)];
  if (sr.battery_kw.some((v) => v != null)) series.push(line("Batteri", sr.battery_kw, HIST_COL.battery));
  chart.setOption({
    grid: { left: 52, right: 16, top: 30, bottom: 36 },
    legend: { top: 0, textStyle: { color: "#93a0b8" } },
    tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "–" : `${v.toFixed(2)} kW`) },
    xAxis: { type: "category", data: sr.t.map(fmtT), axisLabel: { color: "#93a0b8" }, axisLine: { lineStyle: { color: "#93a0b8" } } },
    yAxis: { type: "value", name: "kW", nameTextStyle: { color: "#93a0b8" }, axisLabel: { color: "#93a0b8" }, splitLine: { lineStyle: { color: "rgba(255,255,255,.08)" } } },
    series,
  });
  new ResizeObserver(() => chart.resize()).observe(el);
}

async function renderHistorik() {
  const main = document.getElementById("main");
  main.innerHTML = `<div class="placeholder">Laddar…</div>`;
  let d, log;
  try { [d, log] = await Promise.all([api("api/energyhistory?range=" + histRange), api("api/historylog").catch(() => null)]); }
  catch (e) { main.innerHTML = `<div class="placeholder">${esc(e.message)}</div>`; return; }
  const logHtml = log && log.ok ? `
    <div class="card">
      <h2>📜 Logg</h2>
      <div class="loglist">
        ${log.entries.length ? log.entries.map(e => `<div class="logrow"><div class="t">${new Date(e.ts).toLocaleString("sv-SE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</div><div>${e.user ? `<b>${esc(e.user)}:</b> ` : ""}${esc(e.text || "")}</div></div>`).join("") : `<div class="note">Inget loggat än.</div>`}
      </div>
    </div>` : "";
  const draw = () => {
    main.innerHTML = historyHtml(d) + logHtml;
    historyChart(d.series);
    main.querySelectorAll("#histperiod button").forEach((b) => b.onclick = () => { histPeriod = b.dataset.v; try { localStorage.setItem("ew_hist_period", histPeriod); } catch (e) {} draw(); });
    main.querySelectorAll("#histrange button").forEach((b) => b.onclick = async () => {
      histRange = b.dataset.v; try { localStorage.setItem("ew_hist_range", histRange); } catch (e) {}
      try { d = await api("api/energyhistory?range=" + histRange); } catch (e) { /* behåll förra */ }
      draw();
    });
  };
  if (!d.ok) { main.innerHTML = `<div class="placeholder">Ingen data än</div>` + logHtml; return; }
  draw();
}

async function renderAviseringar() {
  const d = await loadPage("api/notifications", (d) => `
    <div class="card">
      <h2>🔔 Aviseringstyper</h2>
      <div class="note" style="margin-bottom:8px">Styr vilka händelser som skickar en avisering - samma inställning som i mobilappen.</div>
      ${d.items.map(i => `<div class="togglerow"><span>${esc(i.label)}</span><label class="switch"><input type="checkbox" class="notify-toggle" data-key="${i.key}" ${i.on ? "checked" : ""}><span class="slider"></span></label></div>`).join("")}
    </div>`);
  if (d) document.querySelectorAll(".notify-toggle").forEach(cb => {
    cb.onchange = () => api(`api/notifications/${cb.dataset.key}`, { method: "POST", body: JSON.stringify({ value: cb.checked }) }).catch(() => { cb.checked = !cb.checked; });
  });
}

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

let _toastT = null;
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(_toastT);
  _toastT = setTimeout(() => t.classList.remove("show"), 3200);
}

// Skriv-knapparna proxas vidare till ewapp (se webdashboard/app.py:s _ewapp_proxy) -
// samma kommandon som mobilappens knappar, ingen egen hårdvarulogik här.
async function postAction(path, body, okMsg) {
  try {
    const d = await api(path, { method: "POST", body: JSON.stringify(body || {}) });
    toast(okMsg || d.msg || "Klart");
    return d;
  } catch (e) {
    toast("⚠️ " + e.message);
    throw e;
  }
}

async function api(path, opts) {
  const r = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opts });
  if (r.status === 401) { showLogin(); throw new Error("not authed"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

function showLogin() {
  hideSetup();
  mountLangSelect("loginlang", false);
  document.getElementById("login").classList.remove("off");
  document.getElementById("shell").classList.remove("on");
}

function showShell() {
  document.getElementById("login").classList.add("off");
  document.getElementById("shell").classList.add("on");
}

function renderSidebar() {
  const nav = document.getElementById("sidebar");
  nav.innerHTML = PAGES.map(p =>
    `<button class="navitem${p.id === currentPage ? " on" : ""}" data-page="${p.id}">${p.icon} ${p.name}</button>`
  ).join("");
  nav.innerHTML += `<a class="navitem sponsor" href="${SPONSOR_URL}" target="_blank" rel="noopener">❤️ Sponsra EnergyWizard</a>`;
  nav.querySelectorAll(".navitem[data-page]").forEach(b => b.onclick = () => openPage(b.dataset.page));
}

// ---------- Sponsring: länk överallt + en vänlig ruta en gång i månaden (kan stängas av) ----------
const SPONSOR_URL = "https://github.com/sponsors/murre87";
async function showSponsorBanner() {
  const el = document.getElementById("sponsorbanner");
  let st;
  try { st = await api("api/sponsor?lang=" + (window.I18N ? I18N.lang : "sv")); } catch (e) { return; }
  if (!st || !st.show) { el.hidden = true; return; }
  el.innerHTML = `<div class="sponsorcard" data-noi18n>
      <div style="font-size:1.6rem">❤️</div>
      <div class="txt"><b>${esc(st.title)}</b><div style="margin-top:6px">${esc(st.text)}</div>
        <div class="btns"><a class="go" href="${esc(st.url)}" target="_blank" rel="noopener">${esc(st.button)}</a>
        <button class="icobtn" id="sponsorlater">${I18N.lang === "sv" ? "Inte nu" : "Not now"}</button></div></div></div>`;
  el.hidden = false;
  const close = () => { el.hidden = true; api("api/sponsor/dismiss", { method: "POST" }).catch(() => {}); };
  document.getElementById("sponsorlater").onclick = close;
  el.querySelector("a.go").addEventListener("click", close);
}

const BAT_STYLES = {
  very_careful: ["Mycket försiktig", "Planerar för en dålig dag: mycket mindre sol och mer förbrukning än prognosen. Sparar mest i batteriet."],
  careful: ["Försiktig", "Räknar med lite mindre sol och lite mer förbrukning än prognosen."],
  balanced: ["Balanserad", "Planerar på prognosen och sparar en del i batteriet till senare. Standard."],
  bold: ["Djärv", "Planerar nära prognosen och använder batteriet mer."],
  very_bold: ["Mycket djärv", "Planerar på prognosen som den är. Tjänar mest när den stämmer och kostar mer när den slår fel."],
};
async function mountBatteryPlanSettings() {
  let d;
  try { d = await api("api/battery-plan-settings"); } catch (e) { return; }
  if (!d.has_battery) return;
  document.getElementById("batplancard").hidden = false;
  const draw = () => {
    document.getElementById("batstyle").innerHTML = d.styles.map((k) =>
      `<button class="icobtn${k === d.style ? " on" : ""}" data-style="${k}" style="${k === d.style ? "outline:2px solid var(--acc)" : ""}">${esc(BAT_STYLES[k][0])}</button>`).join("");
    document.getElementById("batstyledesc").textContent = BAT_STYLES[d.style][1];
    document.querySelectorAll("#batstyle [data-style]").forEach((b) => b.onclick = async () => {
      try { await postJSON("api/battery-plan-settings", { style: b.dataset.style }); d.style = b.dataset.style; draw(); toast("Sparat - gäller från nästa plan (inom 15 min)"); }
      catch (e) { toast(e.message); }
    });
  };
  draw();
  const cb = document.getElementById("batexport");
  cb.checked = d.allow_export;
  cb.onchange = () => postJSON("api/battery-plan-settings", { allow_export: cb.checked }).catch(() => { cb.checked = !cb.checked; });
}

function mountLangSelect(slotId, saveForInstall) {
  const slot = document.getElementById(slotId);
  if (!slot || !window.I18N) return;
  I18N.ready.then(() => {
    slot.innerHTML = I18N.selectHtml(slotId + "_sel");
    document.getElementById(slotId + "_sel").onchange = async (e) => {
      const lang = e.target.value;
      if (saveForInstall) { try { await postJSON("api/setup/language", { language: lang }); } catch (err) { /* bara den här enheten */ } }
      I18N.set(lang);
    };
  });
}

async function renderVarmepump() {
  const main = document.getElementById("main");
  main.innerHTML = `<div class="placeholder">Laddar…</div>`;
  const d = await api("api/overview");
  if (!d.ok) { main.innerHTML = `<div class="placeholder">${d.error || "Kunde inte läsa data"}</div>`; return; }
  main.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">♨️ Värmepump</div>
      <div class="note" style="margin-top:4px">Ute ${fmt(d.outdoor_temp, 1, "°C")} · Inne ${fmt(d.indoor_temp, 1, "°C")} (mål ${d.indoor_target.toFixed(0)}°C)</div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>🔋 Varmvattenberedaren som värmebatteri</h2>
      <div class="note">Laddas till ${d.heat_battery ? d.heat_battery.ceiling.toFixed(0) : "–"}°C när elen är billig eller solen räcker - töms (kompressorn vilar) när elen är dyr.</div>
      <div style="margin-top:18px">${heatBatteryHtml(d.heat_battery, false)}</div>
    </div>
    <div class="grid" style="margin-bottom:16px">
      <div class="card">
        <h2>🌡️ Rumsvärme</h2>
        <div class="note" style="margin-bottom:8px">Auto = AI:n styr efter elpriset (normalläget). Tvinga PÅ/AV håller tills du väljer Auto igen.</div>
        <div class="seg" id="heatseg">${["auto", "on", "off"].map(m => `<button data-m="${m}" class="${d.heat_mode === m ? "on" : ""}">${{ auto: "Auto", on: "Tvinga PÅ", off: "Tvinga AV" }[m]}</button>`).join("")}</div>
      </div>
      <div class="card">
        <h2>🚿 Varmvatten</h2>
        <div class="note" style="margin-bottom:8px">Samma princip som rumsvärmen, egen överstyrning.</div>
        <div class="seg" id="hotwaterseg">${["auto", "on", "off"].map(m => `<button data-m="${m}" class="${d.hotwater_mode === m ? "on" : ""}">${{ auto: "Auto", on: "Tvinga PÅ", off: "Tvinga AV" }[m]}</button>`).join("")}</div>
      </div>
    </div>
    <div class="card">
      <h2>🎯 Måltemperatur (Auto-läget)</h2>
      <div class="note">Vid billig el / Auto: ${fmt(d.temp_cheap, 1, "°C")} · Vid dyr el: ${fmt(d.temp_expensive, 1, "°C")}</div>
      <div class="numfield" style="margin-top:10px">Billigt: <input type="number" id="tempcheap" step="0.5" min="16" max="26" value="${d.temp_cheap != null ? d.temp_cheap : ""}"> °C
        Dyrt: <input type="number" id="tempexpensive" step="0.5" min="14" max="24" value="${d.temp_expensive != null ? d.temp_expensive : ""}"> °C
        <button class="icobtn" id="savetempbtn">Spara</button></div>
    </div>`;
  document.querySelectorAll("#heatseg button").forEach(b => b.onclick = () => postAction("api/home-action/heat", { value: b.dataset.m }).then(renderVarmepump));
  document.querySelectorAll("#hotwaterseg button").forEach(b => b.onclick = () => postAction("api/home-action/hotwater", { value: b.dataset.m }).then(renderVarmepump));
  document.getElementById("savetempbtn").onclick = async () => {
    await postAction("api/settings-action", { key: "temp_cheap", value: parseFloat(document.getElementById("tempcheap").value) });
    await postAction("api/settings-action", { key: "temp_expensive", value: parseFloat(document.getElementById("tempexpensive").value) });
    renderVarmepump();
  };
}

async function renderSystem() {
  const main = document.getElementById("main");
  main.innerHTML = `<div class="placeholder">Laddar…</div>`;
  await loadUpdates(false);
  const d = await api("api/installs").catch(() => null);
  if (d && d.configured) main.insertAdjacentHTML("afterbegin", installsCard(d));
}

// Utvecklarens egen räknare: aktiva installationer och deras utrustning (telemetrin, bara märken och drivrutiner).
const INSTALL_CATS = [["heatpump", "🌡️", "Värmepump"], ["spa", "🛁", "Spabad"], ["solar", "☀️", "Solceller / växelriktare"],
  ["battery", "🔋", "Husbatteri"], ["charger", "🔌", "Laddbox"], ["car", "🚗", "Elbil"]];
const DRIVER_NAMES = { thermia_husdata: "Thermia (Husdata)", generic_climate: "climate i HA", nibe_local: "NIBE S (lokalt)",
  myuplink: "myUplink", heishamon: "Panasonic (HeishaMon)", solaredge: "SolarEdge", generic_number: "exportgräns i HA",
  huawei_solar: "Huawei", modbus_register: "Modbus-register", gecko: "Gecko", balboa: "Balboa", switch: "relä/brytare",
  shelly: "Shelly", generic: "generisk", easee: "Easee", tesla: "Tesla", nissan: "Nissan", generic_ev: "generisk elbil" };
function installsCard(d) {
  if (!d.ok) return `<div class="card" style="margin-bottom:16px">👥 ${esc(d.error || "")}</div>`;
  const label = (k) => { const [drv, brand] = k.split("@"); return brand ? `${esc(brand)} <span class="note">(${esc(DRIVER_NAMES[drv] || drv)})</span>` : esc(DRIVER_NAMES[drv] || drv); };
  const cats = INSTALL_CATS.map(([key, ico, name]) => {
    const items = Object.entries((d.equipment || {})[key] || {});
    const body = items.length ? items.map(([k, n]) => `<div style="display:flex;justify-content:space-between;gap:10px;padding:3px 0"><span>${label(k)}</span><b>${n}</b></div>`).join("")
      : `<div class="note">–</div>`;
    return `<div class="card" style="padding:12px"><div style="font-weight:700;margin-bottom:6px">${ico} ${name}</div>${body}</div>`;
  }).join("");
  return `<div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">👥 Installationer</div>
      <div style="display:flex;gap:28px;flex-wrap:wrap;margin-top:10px">
        <div><div style="font-size:2rem;font-weight:800">${d.active}</div><div class="note">aktiva (hörda senaste ${d.active_days} dygnen)</div></div>
        <div><div style="font-size:2rem;font-weight:800">${d.total_known}</div><div class="note">totalt sedan start</div></div>
        <div><div style="font-size:2rem;font-weight:800">${d.new_last_7d}</div><div class="note">nya senaste veckan</div></div>
      </div>
      ${d.without_devices ? `<div class="note" style="margin-top:8px">${d.without_devices} har inte valt några enheter än.</div>` : ""}
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:10px;margin-top:14px">${cats}</div>
      <div class="note" style="margin-top:10px">Från telemetrin: bara drivrutin och märke, aldrig vem eller var. Den som stängt av telemetrin syns inte.</div>
    </div>`;
}

async function loadUpdates(force) {
  const main = document.getElementById("main");
  const d = await api(`api/updates${force ? "?force=1" : ""}`);
  if (!d.ok) { main.innerHTML = `<div class="placeholder">${d.error}</div>`; return; }
  const when = d.checked_at ? new Date(d.checked_at * 1000).toLocaleString("sv-SE") : "–";
  const rows = d.pending.length
    ? d.pending.map(n => `<div class="card" style="margin-bottom:8px">🆕 <b>${n}</b> <span class="note">har en nyare version - Watchtower uppdaterar den vid nästa schemalagda körning (08:00)</span></div>`).join("")
    : `<div class="card">✅ Allt uppdaterat - inga nya versioner hittade bland ${d.total} containrar.</div>`;
  main.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">🛠️ Systemuppdateringar</div>
      <div class="note" style="margin-top:4px">Watchtower håller koll på alla ${d.total} containrar på servern och uppdaterar dem automatiskt. Senast kollad: ${when}.</div>
      <button class="icobtn" id="checknowbtn" style="margin-top:10px">Kolla nu</button>
    </div>
    ${rows}`;
  document.getElementById("checknowbtn").onclick = () => loadUpdates(true);
}

let _discovered = null;

async function renderInstallningar() {
  const main = document.getElementById("main");
  main.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">⚙️ Entitetsväljare</div>
      <div class="note" style="margin-top:4px">Skannar ditt Home Assistant efter värmepump, bilar, solceller, batteri, spa och laddare. Kryssa i det som stämmer och tryck <b>Spara och starta</b>.</div>
      <button class="icobtn" id="scanbtn" style="margin-top:10px">Skanna mitt Home Assistant</button>
    </div>
    <div class="card" style="margin-bottom:16px" id="batplancard" hidden>
      <div style="font-size:1.1rem;font-weight:700">🔋 Batteriets planering</div>
      <div class="note" style="margin-top:4px">Hur mycket planen litar på prognosen för sol och förbrukning. Säkerhetsgränserna är desamma i alla stilar.</div>
      <div class="seg" id="batstyle" style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap"></div>
      <div style="display:flex;justify-content:space-between;font-size:.8rem;opacity:.7;margin-top:4px"><span>Sparar mer i batteriet</span><span>Litar mer på prognosen</span></div>
      <div class="note" id="batstyledesc" style="margin-top:8px"></div>
      <label style="display:flex;gap:8px;align-items:flex-start;margin-top:12px"><input type="checkbox" id="batexport">
        <span>Tillåt batteriet att sälja till nätet när planen räknar med en lönsam försäljning.<br><span class="note">Av: batteriet täcker bara husets egen förbrukning. Solelen kan fortfarande säljas.</span></span></label>
    </div>
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">🌍 Språk / Language</div>
      <div class="note" style="margin-top:4px">Gäller hela installationen och alla enheter som inte valt eget språk.</div>
      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center"><span id="setlang"></span>
        <a class="icobtn" href="https://github.com/murre87/energywizard/blob/main/TRANSLATING.md" target="_blank" rel="noopener">Hjälp till att översätta</a>
        <button class="icobtn" id="missingbtn" hidden>Ladda ner texter som saknar översättning</button></div>
      <div class="note" style="margin-top:8px">Översättningarna är vanliga textfiler på GitHub. Vem som helst kan rätta en text eller lägga till ett nytt språk.</div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">❤️ Sponsra EnergyWizard</div>
      <div class="note" style="margin-top:4px">EnergyWizard är gratis och byggs på fritiden. Ett litet bidrag hjälper till att betala för utvecklingen.</div>
      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <a class="icobtn" href="${SPONSOR_URL}" target="_blank" rel="noopener">Sponsra på GitHub</a>
        <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="sponsornotice"> Påminn mig en gång i månaden</label></div>
    </div>
    <div class="card" style="margin-bottom:16px" id="hacard" hidden>
      <div style="font-size:1.1rem;font-weight:700">🏠 Home Assistant</div>
      <div class="note" style="margin-top:4px" id="hainfo"></div>
      <button class="icobtn" id="habtn" style="margin-top:10px">Ändra anslutning</button>
    </div>
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:700">📡 Sök Modbus-värmepump på nätverket</div>
      <div class="note" style="margin-top:4px">Om din värmepump inte syns i Home Assistant alls (pratar direkt Modbus) kan den här knappen leta upp den på ditt lokala nätverk istället. Kan ta upp till en minut - söker bara, ändrar inget.</div>
      <button class="icobtn" id="scanmodbusbtn" style="margin-top:10px">Sök Modbus-värmepump på nätverket</button>
    </div>
    <div id="modbusScanResults"></div>
    <div id="discoverResults"></div>`;
  document.getElementById("scanbtn").onclick = runDiscovery;
  document.getElementById("scanmodbusbtn").onclick = runModbusScan;
  mountLangSelect("setlang", true);
  mountBatteryPlanSettings();
  if (window.I18N && I18N.lang !== "sv") {
    const mb = document.getElementById("missingbtn");
    mb.hidden = false; mb.onclick = () => I18N.downloadMissing();
  }
  api("api/sponsor").then(sp => {
    const cb = document.getElementById("sponsornotice");
    cb.checked = sp.enabled;
    cb.onchange = () => postJSON("api/sponsor/notice", { enabled: cb.checked }).catch(() => { cb.checked = !cb.checked; });
  }).catch(() => {});
  setupStatus().then(st => {
    if (!st || st.supervisor || st.ha_from_env || st.ha_url === undefined) return;
    document.getElementById("hacard").hidden = false;
    document.getElementById("hainfo").textContent = st.ha_ok ? `Kopplat till ${st.ha_url}.` : "Inte kopplat.";
    document.getElementById("habtn").onclick = () => setupHA(3, st.ha_url);
  });
}

async function runModbusScan() {
  const results = document.getElementById("modbusScanResults");
  results.innerHTML = `<div class="placeholder">Söker på nätverket... (kan ta upp till en minut)</div>`;
  let d;
  try { d = await api("api/discover-modbus", { method: "POST" }); } catch (e) { results.innerHTML = `<div class="placeholder">${e.message}</div>`; return; }
  if (!d.ok) { results.innerHTML = `<div class="placeholder">${d.error}</div>`; return; }
  if (!d.found.length) { results.innerHTML = `<div class="note">Ingen Husdata-värmepump hittades på nätverket.</div>`; return; }
  results.innerHTML = `<div class="card" style="margin-bottom:16px"><h2>📡 Hittat på nätverket</h2>` +
    d.found.map(f => `<div class="note">Husdata-pump hittad på <b>${f.ip}</b> - lägg till <code>PUMP_IP=${f.ip}</code> i din .env och starta om smartbox.</div>`).join("") +
    `</div>`;
}

async function runDiscovery() {
  const results = document.getElementById("discoverResults");
  results.innerHTML = `<div class="placeholder">Skannar... (kan ta en liten stund)</div>`;
  let d;
  try { d = await api("api/discover", { method: "POST" }); } catch (e) { results.innerHTML = `<div class="placeholder">${e.message}</div>`; return; }
  if (!d.ok) { results.innerHTML = `<div class="placeholder">${d.error}</div>`; return; }
  _discovered = d;

  const driverTag = (item, genericKey) => {
    if (item.driver_known) return `<span class="tag">drivrutin: ${item.driver}</span>`;
    const base = `<span class="tag warn">hittades (${item.maker || "okänt märke"}) - ingen drivrutin än, bidra gärna</span>`;
    if (!item.generic_suggestion || !genericKey) return base;
    return base + `<label style="display:block;margin-top:4px;font-size:.8rem">
      <input type="checkbox" class="generic-pick" data-key="${genericKey}"> Använd generisk styrning (grundläggande, inte märkets fulla funktioner)</label>`;
  };

  let html = "";

  html += `<div class="card" style="margin-bottom:16px"><h2>🚗 Bilar (${d.cars.length})</h2>`;
  d.cars.forEach((c, i) => {
    html += `<div class="note" style="margin:10px 0;padding:10px;border:1px solid var(--line);border-radius:10px">
      <label><input type="checkbox" class="car-pick" data-i="${i}" checked> <b>${c.device_name}</b></label> ${driverTag(c)}<br>
      id: <input type="text" class="car-id" data-i="${i}" value="${c.driver}" style="width:100px"> &nbsp;
      batteri (kWh): <input type="number" class="car-kwh" data-i="${i}" value="60" style="width:70px"><br>
      <span style="font-size:.8rem">SOC: ${c.soc_entity || "-"} · Kabel: ${c.plugged_in_entity || "-"} · Klimat: ${c.climate_entity || "-"}</span>
    </div>`;
  });
  if (!d.cars.length) html += `<div class="note">Inga bilar hittades.</div>`;
  html += `</div>`;

  const simpleCard = (icon, title, item, fields) => {
    if (!item) return `<div class="card" style="margin-bottom:16px"><h2>${icon} ${title}</h2><div class="note">Inget hittades i Home Assistant${title === "Värmepump" ? " - normalt om din pump pratar direkt via Modbus istället för via en HA-integration (t.ex. Thermia/Husdata). Sätt heat_pump.enabled: true och fyll i anslutningen för hand i den nedladdade filen efteråt." : ""}.</div></div>`;
    return `<div class="card" style="margin-bottom:16px"><h2>${icon} ${title}</h2>
      <label><input type="checkbox" class="pick" data-cat="${title}" checked> Använd detta fynd</label> ${driverTag(item, title)}
      <div class="note" style="margin-top:6px;font-size:.8rem">${fields}</div></div>`;
  };
  html += simpleCard("♨️", "Värmepump", d.heat_pump, d.heat_pump ? (d.heat_pump.note || `${d.heat_pump.device_name} (${d.heat_pump.entity_count} entiteter)`) : "");
  html += simpleCard("☀️", "Solceller", d.solar, d.solar ? `Effekt: ${d.solar.pv_power_entity || "-"} · Dagsenergi: ${d.solar.today_kwh_entity || "-"}` : "");
  html += simpleCard("🛁", "Spabad", d.spa, d.spa ? `Temp: ${d.spa.current_temp_entity || "-"} · Effekt: ${d.spa.power_entity || "-"}` : "");
  html += simpleCard("🔋", "Husbatteri", d.battery, d.battery ? `SOC: ${d.battery.soc_entity || "-"} · Effekt: ${d.battery.power_entity || "-"} · bara läsning/enkel styrning, EnergyWizard fattar inga automatiska laddningsbeslut - kör Predbat parallellt för det.` : "");

  html += `<div class="card" style="margin-bottom:16px"><h2>🔌 Laddare (${d.chargers.length})</h2>`;
  d.chargers.forEach((c, i) => {
    html += `<label style="display:block;margin:6px 0"><input type="checkbox" class="charger-pick" data-i="${i}" checked> ${c.device_name}</label> ${driverTag(c, `charger:${i}`)}`;
  });
  if (!d.chargers.length) html += `<div class="note">Inga laddare hittades.</div>`;
  html += `</div>`;

  html += `<div class="card" style="margin-bottom:16px"><h2>⚡ Elmätare / Tibber Pulse</h2>
    <div class="note">Krävs för effektvakten, säkringsskyddet och solladdningen. Bäst är en mätare med ström per fas (t.ex. Tibber Pulse); en smartmätare (HAN/P1) med bara effekt fungerar också.</div>
    ${d.power_meter ? `<label style="display:block;margin:8px 0"><input type="checkbox" class="pick" data-cat="Elmätare" checked> Använd ${d.power_meter.driver === "tibber_pulse" ? "Tibber Pulse (spänning + ström per fas)" : "effektsensorn " + esc(d.power_meter.entities.power_w)}</label>` : ""}`;
  (d.grid_meters || []).forEach(g => {
    html += `<div class="note" style="margin-top:6px">• ${g.kind === "pulse" ? "Tibber Pulse" : "Smartmätare"}: ${g.power_entity} (${g.maker || "okänt märke"})</div>`;
  });
  if (!(d.grid_meters || []).length) html += `<div class="note" style="margin-top:6px">Ingen hittades.</div>`;
  html += `</div>`;

  html += `<button class="icobtn" id="savebtn" style="margin-top:6px;display:none">Spara och starta</button>
    <button class="icobtn" id="genbtn" style="margin-top:6px">Ladda ner house_config.yaml</button>
    <div class="note" id="savemsg" style="margin-top:6px"></div>`;
  results.innerHTML = html;
  document.getElementById("genbtn").onclick = () => generateConfig(false);
  document.getElementById("savebtn").onclick = () => generateConfig(true);
  // Spara direkt bara i installationer där install.sh gjort filen skrivbar; annars bara nedladdning.
  fetch("api/house-config-status", { credentials: "same-origin" }).then(r => r.ok ? r.json() : {}).then(st => {
    if (st && st.writable) document.getElementById("savebtn").style.display = "";
  }).catch(() => {});

  // Kryssar man i "Använd generisk styrning" skrivs fyndets driver/entities om till
  // förslaget (generic_suggestion) - annars tillbaka till det ursprungliga (okänt märke,
  // ingen drivrutin). generateConfig() läser direkt ur _discovered, så det räcker att
  // mutera objektet här, ingen separat state behövs.
  const itemForKey = (key) => key.startsWith("charger:") ? _discovered.chargers[key.split(":")[1]]
    : key === "Värmepump" ? _discovered.heat_pump
    : key === "Solceller" ? _discovered.solar
    : key === "Husbatteri" ? _discovered.battery
    : null;
  document.querySelectorAll(".generic-pick").forEach(cb => {
    cb.onchange = () => {
      const item = itemForKey(cb.dataset.key);
      if (!item || !item.generic_suggestion) return;
      if (cb.checked) {
        item._original_driver_state = { driver: item.driver, entities: item.entities };
        item.driver = item.generic_suggestion.driver;
        item.entities = item.generic_suggestion.entities;
      } else if (item._original_driver_state) {
        item.driver = item._original_driver_state.driver;
        item.entities = item._original_driver_state.entities;
      }
    };
  });
}

async function generateConfig(save) {
  const sel = { cars: [], heat_pump: null, solar: null, spa: null, battery: null };
  const pickedChargers = [];
  document.querySelectorAll(".charger-pick:checked").forEach(cb => pickedChargers.push(_discovered.chargers[cb.dataset.i]));
  document.querySelectorAll(".car-pick:checked").forEach((cb, idx) => {
    const i = cb.dataset.i;
    const car = { ..._discovered.cars[i] };
    car.id = document.querySelector(`.car-id[data-i="${i}"]`).value || car.driver;
    car.battery_kwh = parseFloat(document.querySelector(`.car-kwh[data-i="${i}"]`).value) || 60;
    // Ihopparning laddare<->bil är en gissning (index-ordning) - markerad i YAML:ns
    // kommentar, inte tyst: handskakningen (se main.py) kan ändå byta dem vid behov.
    car.charger = pickedChargers[idx] || null;
    sel.cars.push(car);
  });
  document.querySelectorAll(".pick:checked").forEach(cb => {
    const cat = cb.dataset.cat;
    if (cat === "Värmepump") sel.heat_pump = _discovered.heat_pump;
    if (cat === "Solceller") sel.solar = _discovered.solar;
    if (cat === "Spabad") sel.spa = _discovered.spa;
    if (cat === "Husbatteri") sel.battery = _discovered.battery;
    if (cat === "Elmätare") sel.power_meter = _discovered.power_meter;
  });

  if (save) {
    const msg = document.getElementById("savemsg");
    msg.textContent = "Sparar…";
    const rs = await fetch("api/save-house-config", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sel) });
    const j = await rs.json().catch(() => ({}));
    msg.textContent = rs.ok ? j.message : ("Kunde inte spara: " + (j.error || rs.status));
    return;
  }
  const r = await fetch("api/generate-house-config", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sel) });
  if (!r.ok) { alert("Kunde inte generera filen: " + (await r.json().catch(() => ({}))).error); return; }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "house_config.yaml"; a.click();
  URL.revokeObjectURL(url);
}

function openPage(id) {
  currentPage = id;
  renderSidebar();
  closeMobileMenu();
  if (id === "oversikt") {
    renderOversikt();
  } else if (id === "varmepump") {
    renderVarmepump();
  } else if (id === "system") {
    renderSystem();
  } else if (id === "installningar") {
    renderInstallningar();
  } else if (id === "elbil") {
    renderElbil();
  } else if (id === "solceller") {
    renderSolceller();
  } else if (id === "ekonomi") {
    renderEkonomi();
  } else if (id === "elforbrukning") {
    renderElforbrukning();
  } else if (id === "spabad") {
    renderSpabad();
  } else if (id === "temperaturer") {
    renderTemperaturer();
  } else if (id === "prognos") {
    renderPrognos();
  } else if (id === "historik") {
    renderHistorik();
  } else if (id === "aviseringar") {
    renderAviseringar();
  } else {
    document.getElementById("main").innerHTML = `<div class="placeholder">"${PAGES.find(p => p.id === id)?.name}" byggs i en senare fas.</div>`;
  }
}

// ---------- Startguiden (första start): lösenord -> Home Assistant -> prylar ----------
async function setupStatus() {
  try { const r = await fetch("api/setup/status", { credentials: "same-origin" }); return r.ok ? r.json() : null; }
  catch (e) { return null; }
}

function showSetup(step, total, title, bodyHtml, btnText, onSubmit) {
  document.getElementById("login").classList.remove("off");
  document.getElementById("shell").classList.remove("on");
  document.getElementById("loginform").style.display = "none";
  const f = document.getElementById("setupform");
  f.style.display = "";
  document.getElementById("setupstep").textContent = `Steg ${step} av ${total}: ${title}`;
  document.getElementById("setupbody").innerHTML = bodyHtml;
  document.getElementById("setuperr").textContent = "";
  document.getElementById("setupok").textContent = "";
  const btn = document.getElementById("setupbtn");
  btn.textContent = btnText;
  btn.disabled = false;
  f.onsubmit = async (e) => {
    e.preventDefault();
    btn.disabled = true;
    document.getElementById("setuperr").textContent = "";
    try { await onSubmit(); } catch (err) { document.getElementById("setuperr").textContent = err.message || String(err); btn.disabled = false; }
  };
  const first = f.querySelector("input"); if (first) first.focus();
}

function hideSetup() {
  document.getElementById("setupform").style.display = "none";
  document.getElementById("loginform").style.display = "";
}

async function postJSON(path, body) {
  const r = await fetch(path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.statusText);
  return j;
}

function setupPassword(total) {
  mountLangSelect("setuplang", true);
  showSetup(1, total, "välj lösenord",
    `<div class="note">Lösenordet skyddar webben och mobilappen. Logga in med det sedan (användarnamn behövs inte).</div>
     <input type="password" id="s_pw" placeholder="Lösenord, minst 8 tecken" autocomplete="new-password" required minlength="8">
     <input type="password" id="s_pw2" placeholder="Samma lösenord igen" autocomplete="new-password" required>`,
    "Spara lösenord", async () => {
      const a = document.getElementById("s_pw").value, b = document.getElementById("s_pw2").value;
      if (a !== b) throw new Error("Lösenorden är inte lika.");
      await postJSON("api/setup/password", { password: a });
      boot();
    });
}

function setupHA(total, prev) {
  showSetup(2, total, "koppla Home Assistant",
    `<div class="note">EnergyWizard läser och styr allt via Home Assistant.</div>
     <input type="text" id="s_url" placeholder="Adress, t.ex. 192.168.1.10 eller http://homeassistant.local:8123" value="${esc(prev || "")}" required>
     <input type="password" id="s_tok" placeholder="Token" required>
     <details class="note"><summary>Var hittar jag token?</summary>
       I Home Assistant: klicka på ditt namn längst ner till vänster, välj fliken <b>Säkerhet</b>,
       scrolla längst ner till <b>Långlivade åtkomsttoken</b> och tryck <b>Skapa token</b>. Kopiera den och klistra in här.
     </details>`,
    "Testa och spara", async () => {
      const j = await postJSON("api/setup/ha", { url: document.getElementById("s_url").value, token: document.getElementById("s_tok").value });
      document.getElementById("setupok").textContent = j.message || "Kopplat!";
      setTimeout(boot, 900);
    });
}

async function boot() {
  const st = await setupStatus();
  const total = st && st.supervisor ? 2 : 3;
  if (st && st.needs_password) { setupPassword(total); return; }
  try {
    const me = await api("api/me");
    if (!me.role) { showLogin(); return; }
    hideSetup();
    PAGES = me.pages;
    if (st && me.role === "owner" && !st.ha_ok && !st.supervisor) { setupHA(total, st.ha_url); return; }
    showShell();
    if (me.role === "owner") showSponsorBanner();
    if (st && me.role === "owner" && !st.devices_chosen) { openPage("installningar"); return; }
    openPage("oversikt");
  } catch (e) { showLogin(); }
}

document.getElementById("loginform").onsubmit = async (e) => {
  e.preventDefault();
  const err = document.getElementById("loginerr");
  err.textContent = "";
  try {
    await api("api/login", { method: "POST", body: JSON.stringify({ user: document.getElementById("user").value, password: document.getElementById("pw").value }) });
    boot();
  } catch (e) { err.textContent = e.message || "Fel användarnamn eller lösenord"; }
};

document.getElementById("logoutbtn").onclick = async () => { await api("api/logout", { method: "POST" }); showLogin(); };

function closeMobileMenu() {
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("sidebarbackdrop").classList.remove("open");
}
document.getElementById("menubtn").onclick = () => {
  document.getElementById("sidebar").classList.toggle("open");
  document.getElementById("sidebarbackdrop").classList.toggle("open");
};
document.getElementById("sidebarbackdrop").onclick = closeMobileMenu;

boot();
