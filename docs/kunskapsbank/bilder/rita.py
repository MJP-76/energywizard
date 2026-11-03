"""Ritar kunskapsbankens bilder (SVG) på svenska och engelska. Kör: python3 docs/kunskapsbank/bilder/rita.py

Färger som sajten (docs/style.css): mörk bakgrund, grön = sol/laddning, blå = nät, gul = batteri, röd = dyrt.
Siffrorna i stilbilden kommer från smartbox/battery_plan.py PLAN_STYLES (läses därifrån, inte inskrivna).
"""
import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BG, CARD, LINE, TXT, MUT = "#0b1220", "#141c2c", "#2a3446", "#f3f6fb", "#93a0b8"
SUN, GRID, BAT, HOUSE, RED = "#22d3a0", "#38bdf8", "#fbbf24", "#c4b5fd", "#f87171"
FONT = "font-family='Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif'"

T = {
    "sv": {
        "intents_title": "Batteriets fem lägen",
        "sun": "Sol", "house": "Hus", "grid": "Nät", "bat": "Batteri",
        "auto": ("Auto", "Täcker huset, tar solöverskott"),
        "hold": ("Håll", "Tar solöverskott, laddar inte ur"),
        "idle": ("Vila", "Varken laddar eller laddar ur"),
        "charge": ("Ladda", "Laddar fullt, även från nätet"),
        "discharge": ("Ladda ur", "Laddar ur fullt, överskott säljs"),
        "styles_title": "Planeringsstil: hur mycket planen litar på prognosen",
        "styles": ["Mycket\nförsiktig", "Försiktig", "Balanserad", "Djärv", "Mycket\ndjärv"],
        "s_sun": "Solprognos räknas som", "s_load": "Förbrukning räknas som", "s_keep": "Sparar kvar i batteriet",
        "s_note": "Säkerhetsgränserna (reservnivå, säkring, effekttak) är desamma i alla stilar.",
        "keep": ["mest", "mer", "normalt", "mindre", "minst"],
        "day_title": "Exempel: ett dygn med dygnsplanen",
        "price": "Elpris", "plan": "Batteriet", "soc": "Laddnivå",
        "a_charge": "laddar billigt", "a_auto": "täcker huset", "a_hold": "sparar", "a_dis": "laddar ur dyrt",
        "export_title": "Får batteriet sälja till nätet?",
        "ex_on": "På: batteriet kan laddas ur mot nätet när priset är högt",
        "ex_off": "Av: batteriet täcker bara husets egen förbrukning",
        "sell": "säljs",
    },
    "en": {
        "intents_title": "The battery's five modes",
        "sun": "Solar", "house": "House", "grid": "Grid", "bat": "Battery",
        "auto": ("Auto", "Covers the house, takes solar surplus"),
        "hold": ("Hold", "Takes solar surplus, no discharge"),
        "idle": ("Idle", "Neither charges nor discharges"),
        "charge": ("Charge", "Full charge, also from the grid"),
        "discharge": ("Discharge", "Full discharge, surplus is sold"),
        "styles_title": "Planning style: how much the plan trusts the forecast",
        "styles": ["Very\ncareful", "Careful", "Balanced", "Bold", "Very\nbold"],
        "s_sun": "Solar forecast counted as", "s_load": "Consumption counted as", "s_keep": "Keeps in the battery",
        "s_note": "The safety limits (reserve level, main fuse, peak cap) are the same in every style.",
        "keep": ["most", "more", "normal", "less", "least"],
        "day_title": "Example: one day with the daily plan",
        "price": "Price", "plan": "Battery", "soc": "Charge level",
        "a_charge": "charges cheap", "a_auto": "covers the house", "a_hold": "saves", "a_dis": "discharges expensive",
        "export_title": "May the battery sell to the grid?",
        "ex_on": "On: the battery may discharge to the grid when prices are high",
        "ex_off": "Off: the battery only covers the house's own consumption",
        "sell": "sold",
    },
}


def svg(w, h, body, title):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img' "
            f"aria-label='{title.replace(chr(39), '&#39;')}' {FONT}>\n<rect width='{w}' height='{h}' rx='18' fill='{BG}'/>\n{body}\n</svg>\n")


def text(x, y, s, size=15, fill=TXT, anchor="start", weight=400):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return f"<text x='{x}' y='{y}' font-size='{size}' fill='{fill}' text-anchor='{anchor}' font-weight='{weight}'>{s}</text>"


def node(x, y, label, color, icon, above=False):
    ly = y - 30 if above else y + 40
    return (f"<circle cx='{x}' cy='{y}' r='22' fill='{color}' fill-opacity='.16' stroke='{color}' stroke-width='2'/>"
            + text(x, y + 6, icon, 18, color, "middle") + text(x, ly, label, 11, MUT, "middle"))


def arrow(x1, y1, x2, y2, color, dashed=False):
    d = " stroke-dasharray='5 5'" if dashed else ""
    return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' stroke-width='3' "
            f"marker-end='url(#a{color[1:]})'{d}/>")


def markers():
    return "<defs>" + "".join(
        f"<marker id='a{c[1:]}' viewBox='0 0 10 10' refX='8' refY='5' markerWidth='6' markerHeight='6' orient='auto'>"
        f"<path d='M0,0 L10,5 L0,10 z' fill='{c}'/></marker>" for c in (SUN, GRID, BAT, HOUSE)) + "</defs>"


FLOWS = {
    "auto": [("sun", "house", SUN), ("sun", "bat", SUN), ("bat", "house", BAT)],
    "hold": [("sun", "house", SUN), ("sun", "bat", SUN), ("grid", "house", GRID)],
    "idle": [("sun", "house", SUN), ("grid", "house", GRID)],
    "charge": [("grid", "bat", GRID), ("sun", "bat", SUN), ("grid", "house", GRID)],
    "discharge": [("bat", "house", BAT), ("bat", "grid", BAT)],
}
KEYS = ("auto", "hold", "idle", "charge", "discharge")


def wrap(s, n):
    """Radbryt på ord till högst n tecken per rad."""
    lines, cur = [], ""
    for w in s.split():
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def flow(out, pos, key, r=22):
    for a, b, c in FLOWS[key]:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        dx, dy = x2 - x1, y2 - y1
        n = (dx * dx + dy * dy) ** .5
        out.append(arrow(x1 + dx / n * (r + 4), y1 + dy / n * (r + 4), x2 - dx / n * (r + 8), y2 - dy / n * (r + 8), c,
                         dashed=(key == "discharge" and b == "grid")))


def intents(lang):
    t = T[lang]
    W, H, cw = 1000, 350, 184
    out = [markers(), text(30, 44, t["intents_title"], 22, TXT, weight=700)]
    # för varje läge: sol (överst), nät (vänster), hus (höger), batteri (nederst) + pilar
    flows = FLOWS
    for i, key in enumerate(("auto", "hold", "idle", "charge", "discharge")):
        x0 = 20 + i * (cw + 12)
        name, desc = t[key]
        out.append(f"<rect x='{x0}' y='66' width='{cw}' height='268' rx='14' fill='{CARD}' stroke='{LINE}'/>")
        out.append(text(x0 + cw / 2, 92, name, 17, TXT, "middle", 700))
        cx, cy = x0 + cw / 2, 186
        pos = {"sun": (cx, 138), "grid": (cx - 58, cy), "house": (cx + 58, cy), "bat": (cx, 240)}
        for a, b, c in flows[key]:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            dx, dy = x2 - x1, y2 - y1
            n = (dx * dx + dy * dy) ** .5
            out.append(arrow(x1 + dx / n * 26, y1 + dy / n * 26, x2 - dx / n * 30, y2 - dy / n * 30, c,
                             dashed=(key == "discharge" and b == "grid")))
        out += [node(*pos["sun"], t["sun"], SUN, "☀", above=True), node(*pos["grid"], t["grid"], GRID, "⚡"),
                node(*pos["house"], t["house"], HOUSE, "⌂"), node(*pos["bat"], t["bat"], BAT, "▮")]
        for k, part in enumerate(desc.split(", ")):                  # två rader: "Täcker huset," / "tar solöverskott"
            out.append(text(x0 + cw / 2, 304 + k * 15, part + ("," if k == 0 and ", " in desc else ""), 11.5, MUT, "middle"))
    return svg(W, H, "\n".join(out), t["intents_title"])


def plan_styles():
    src = (ROOT / "smartbox" / "battery_plan.py").read_text(encoding="utf-8")
    block = re.search(r"PLAN_STYLES = (\{.*?\n\})", src, re.S).group(1)
    return list(ast.literal_eval(block).values())          # [(sol, last, percentil), ...] i ordning


def styles(lang):
    t = T[lang]
    vals = plan_styles()
    W, H = 1000, 380
    out = [text(30, 44, t["styles_title"], 22, TXT, weight=700)]
    cols = [RED, "#fb923c", SUN, GRID, "#818cf8"]
    rows = [(t["s_sun"], lambda v: f"{round(v[0] * 100)} %", lambda v: v[0] / 1.1),
            (t["s_load"], lambda v: f"{round(v[1] * 100)} %", lambda v: v[1] / 1.3),
            (t["s_keep"], None, lambda v: v[2] / 55)]
    lx, x0, cw = 30, 250, 140
    for j, name in enumerate(t["styles"]):
        cx = x0 + j * (cw + 8) + cw / 2
        for k, line in enumerate(name.split("\n")):
            out.append(text(cx, 86 + k * 17, line, 14, cols[j], "middle", 700))
    for r, (label, fmt, frac) in enumerate(rows):
        y = 140 + r * 66
        out.append(text(lx, y + 22, label, 14, TXT))
        for j, v in enumerate(vals):
            bx = x0 + j * (cw + 8)
            out.append(f"<rect x='{bx}' y='{y}' width='{cw}' height='34' rx='8' fill='{CARD}' stroke='{LINE}'/>")
            out.append(f"<rect x='{bx}' y='{y}' width='{max(6, cw * min(1, frac(v)))}' height='34' rx='8' "
                       f"fill='{cols[j]}' fill-opacity='.55'/>")
            out.append(text(bx + cw / 2, y + 23, fmt(v) if fmt else t["keep"][j], 14, TXT, "middle", 600))
    out.append(text(30, 356, t["s_note"], 13, MUT))
    return svg(W, H, "\n".join(out), t["styles_title"])


def day(lang):
    """Ett påhittat men typiskt vinterdygn: billig natt, dyra toppar morgon och kväll."""
    t = T[lang]
    price = [42, 38, 35, 33, 34, 40, 78, 125, 140, 110, 82, 70, 62, 60, 66, 80, 118, 160, 172, 150, 110, 80, 60, 48]
    act = ["c"] * 5 + ["h", "h"] + ["d", "d", "d"] + ["a"] * 6 + ["d"] * 4 + ["a"] * 2 + ["c", "c"]
    soc = []
    s = 30
    for a in act:
        s = min(95, s + 13) if a == "c" else max(15, s - 14) if a == "d" else max(15, s - 2) if a == "a" else s
        soc.append(s)
    W, H = 1000, 440
    x0, w = 90, 870
    bw = w / 24
    out = [text(30, 44, t["day_title"], 22, TXT, weight=700)]
    top, ph = 70, 150
    pmax = max(price)
    out.append(text(30, top + 16, t["price"], 13, MUT))
    for h, p in enumerate(price):
        bh = ph * p / pmax
        col = RED if p >= 110 else (SUN if p <= 45 else GRID)
        out.append(f"<rect x='{x0 + h * bw + 2}' y='{top + ph - bh}' width='{bw - 4}' height='{bh}' rx='3' "
                   f"fill='{col}' fill-opacity='.7'/>")
    # batteriband
    by = top + ph + 22
    out.append(text(30, by + 18, t["plan"], 13, MUT))
    colmap = {"c": SUN, "d": BAT, "a": HOUSE, "h": GRID}
    for h, a in enumerate(act):
        out.append(f"<rect x='{x0 + h * bw}' y='{by}' width='{bw}' height='28' fill='{colmap[a]}' fill-opacity='.8'/>")
    # laddnivå som linje
    sy, sh = by + 52, 70
    out.append(text(30, sy + 30, t["soc"], 13, MUT))
    pts = " ".join(f"{x0 + h * bw + bw / 2:.1f},{sy + sh - sh * v / 100:.1f}" for h, v in enumerate(soc))
    out.append(f"<polyline points='{pts}' fill='none' stroke='{BAT}' stroke-width='3' stroke-linejoin='round'/>")
    out.append(f"<line x1='{x0}' y1='{sy + sh}' x2='{x0 + w}' y2='{sy + sh}' stroke='{LINE}'/>")
    for h in range(0, 25, 3):
        out.append(text(x0 + h * bw, sy + sh + 18, f"{h:02d}", 11, MUT, "middle"))
    lx = x0
    for key, col in (("a_charge", SUN), ("a_hold", GRID), ("a_auto", HOUSE), ("a_dis", BAT)):
        out.append(f"<rect x='{lx}' y='{H - 26}' width='14' height='14' rx='3' fill='{col}'/>")
        out.append(text(lx + 20, H - 14, t[key], 13, TXT))
        lx += 200
    return svg(W, H, "\n".join(out), t["day_title"])


def export(lang):
    t = T[lang]
    W, H = 1000, 230
    out = [markers(), text(30, 44, t["export_title"], 22, TXT, weight=700)]
    for i, (key, sell) in enumerate((("ex_on", True), ("ex_off", False))):
        x0 = 20 + i * 490
        out.append(f"<rect x='{x0}' y='64' width='470' height='150' rx='14' fill='{CARD}' stroke='{LINE}'/>")
        bx, hx, gx, y = x0 + 70, x0 + 235, x0 + 400, 130
        out.append(arrow(bx + 26, y, hx - 30, y, BAT))
        if sell:
            out.append(arrow(hx + 26, y, gx - 30, y, BAT, dashed=True))
            out.append(text((hx + gx) / 2, y - 10, t["sell"], 12, BAT, "middle"))
        else:
            out.append(f"<line x1='{hx + 40}' y1='{y - 14}' x2='{gx - 40}' y2='{y + 14}' stroke='{RED}' stroke-width='3'/>"
                       f"<line x1='{hx + 40}' y1='{y + 14}' x2='{gx - 40}' y2='{y - 14}' stroke='{RED}' stroke-width='3'/>")
        out += [node(bx, y, t["bat"], BAT, "▮"), node(hx, y, t["house"], HOUSE, "⌂"), node(gx, y, t["grid"], GRID, "⚡")]
        out.append(text(x0 + 235, 200, t[key], 13, TXT, "middle"))
    return svg(W, H, "\n".join(out), t["export_title"])


# --- mobilversioner (smala, ca 420 px, läsbara på en telefon) ------------------------------------------------------
def legend_row(out, t, y):
    x = 22
    for key, col, icon in (("sun", SUN, "☀"), ("grid", GRID, "⚡"), ("house", HOUSE, "⌂"), ("bat", BAT, "▮")):
        out.append(text(x, y, icon, 15, col) + text(x + 18, y, t[key], 13, MUT))
        x += 96


def intents_m(lang):
    t = T[lang]
    W, rowh = 420, 150
    out = [markers(), text(20, 40, t["intents_title"], 20, TXT, weight=700)]
    legend_row(out, t, 70)
    for i, key in enumerate(KEYS):
        y0 = 90 + i * rowh
        name, desc = t[key]
        out.append(f"<rect x='12' y='{y0}' width='396' height='{rowh - 12}' rx='14' fill='{CARD}' stroke='{LINE}'/>")
        cx, cy = 100, y0 + 69
        pos = {"sun": (cx, cy - 44), "grid": (cx - 58, cy), "house": (cx + 58, cy), "bat": (cx, cy + 44)}
        flow(out, pos, key, r=18)
        for k, (col, icon) in (("sun", (SUN, "☀")), ("grid", (GRID, "⚡")), ("house", (HOUSE, "⌂")), ("bat", (BAT, "▮"))):
            x, y = pos[k]
            out.append(f"<circle cx='{x}' cy='{y}' r='18' fill='{col}' fill-opacity='.16' stroke='{col}' stroke-width='2'/>"
                       + text(x, y + 6, icon, 16, col, "middle"))
        out.append(text(200, cy - 12, name, 19, TXT, weight=700))
        for k, line in enumerate(wrap(desc, 24)):
            out.append(text(200, cy + 14 + k * 20, line, 14, MUT))
    return svg(W, 90 + 5 * rowh + 6, "\n".join(out), t["intents_title"])


def styles_m(lang):
    t = T[lang]
    vals = plan_styles()
    cols = [RED, "#fb923c", SUN, GRID, "#818cf8"]
    W, blk = 420, 132
    out = []
    for k, line in enumerate(wrap(t["styles_title"], 34)):
        out.append(text(20, 38 + k * 25, line, 19, TXT, weight=700))
    top = 38 + 25 * len(wrap(t["styles_title"], 34)) + 6
    rows = [(t["s_sun"], lambda v: f"{round(v[0] * 100)} %", lambda v: v[0] / 1.1),
            (t["s_load"], lambda v: f"{round(v[1] * 100)} %", lambda v: v[1] / 1.3),
            (t["s_keep"], None, lambda v: v[2] / 55)]
    for j, v in enumerate(vals):
        y0 = top + j * blk
        out.append(f"<rect x='12' y='{y0}' width='396' height='{blk - 10}' rx='14' fill='{CARD}' stroke='{LINE}'/>")
        out.append(text(26, y0 + 26, t["styles"][j].replace("\n", " "), 16, cols[j], weight=700))
        for r, (label, fmt, frac) in enumerate(rows):
            y = y0 + 40 + r * 26
            out.append(text(26, y + 15, label, 12.5, MUT))
            bx, bw = 238, 156
            out.append(f"<rect x='{bx}' y='{y}' width='{bw}' height='20' rx='6' fill='{BG}' stroke='{LINE}'/>")
            out.append(f"<rect x='{bx}' y='{y}' width='{max(5, bw * min(1, frac(v)))}' height='20' rx='6' fill='{cols[j]}' fill-opacity='.6'/>")
            out.append(text(bx + bw / 2, y + 15, fmt(v) if fmt else t["keep"][j], 12.5, TXT, "middle", 600))
    y = top + 5 * blk + 14
    for k, line in enumerate(wrap(t["s_note"], 52)):
        out.append(text(20, y + k * 18, line, 13, MUT))
    return svg(W, y + 18 * len(wrap(t["s_note"], 52)) + 8, "\n".join(out), t["styles_title"])


def day_m(lang):
    t = T[lang]
    price = [42, 38, 35, 33, 34, 40, 78, 125, 140, 110, 82, 70, 62, 60, 66, 80, 118, 160, 172, 150, 110, 80, 60, 48]
    act = ["c"] * 5 + ["h", "h"] + ["d", "d", "d"] + ["a"] * 6 + ["d"] * 4 + ["a"] * 2 + ["c", "c"]
    soc, s_ = [], 30
    for a in act:
        s_ = min(95, s_ + 13) if a == "c" else max(15, s_ - 14) if a == "d" else max(15, s_ - 2) if a == "a" else s_
        soc.append(s_)
    W, x0, w = 420, 20, 380
    bw = w / 24
    out = []
    for k, line in enumerate(wrap(t["day_title"], 30)):
        out.append(text(20, 38 + k * 25, line, 19, TXT, weight=700))
    top = 38 + 25 * len(wrap(t["day_title"], 30)) + 8
    out.append(text(x0, top + 6, t["price"], 13, MUT))
    ph, pmax = 140, max(price)
    for h, p in enumerate(price):
        bh = ph * p / pmax
        col = RED if p >= 110 else (SUN if p <= 45 else GRID)
        out.append(f"<rect x='{x0 + h * bw + 1.5}' y='{top + 16 + ph - bh}' width='{bw - 3}' height='{bh}' rx='2' fill='{col}' fill-opacity='.75'/>")
    by = top + 16 + ph + 30
    out.append(text(x0, by - 8, t["plan"], 13, MUT))
    colmap = {"c": SUN, "d": BAT, "a": HOUSE, "h": GRID}
    for h, a in enumerate(act):
        out.append(f"<rect x='{x0 + h * bw}' y='{by}' width='{bw}' height='24' fill='{colmap[a]}' fill-opacity='.85'/>")
    sy, sh = by + 58, 70
    out.append(text(x0, sy - 10, t["soc"], 13, MUT))
    pts = " ".join(f"{x0 + h * bw + bw / 2:.1f},{sy + sh - sh * v / 100:.1f}" for h, v in enumerate(soc))
    out.append(f"<polyline points='{pts}' fill='none' stroke='{BAT}' stroke-width='3' stroke-linejoin='round'/>")
    out.append(f"<line x1='{x0}' y1='{sy + sh}' x2='{x0 + w}' y2='{sy + sh}' stroke='{LINE}'/>")
    for h in range(0, 25, 6):
        out.append(text(x0 + h * bw, sy + sh + 18, f"{h:02d}", 12, MUT, "middle" if 0 < h < 24 else ("start" if h == 0 else "end")))
    ly = sy + sh + 46
    for i, (key, col) in enumerate((("a_charge", SUN), ("a_hold", GRID), ("a_auto", HOUSE), ("a_dis", BAT))):
        lx, yy = x0 + (i % 2) * 195, ly + (i // 2) * 24
        out.append(f"<rect x='{lx}' y='{yy - 12}' width='14' height='14' rx='3' fill='{col}'/>" + text(lx + 20, yy, t[key], 13, TXT))
    return svg(W, ly + 40, "\n".join(out), t["day_title"])


def export_m(lang):
    t = T[lang]
    W = 420
    out = [markers()]
    for k, line in enumerate(wrap(t["export_title"], 34)):
        out.append(text(20, 38 + k * 25, line, 19, TXT, weight=700))
    top = 38 + 25 * len(wrap(t["export_title"], 34))
    for i, (key, sell) in enumerate((("ex_on", True), ("ex_off", False))):
        y0 = top + i * 178
        out.append(f"<rect x='12' y='{y0}' width='396' height='166' rx='14' fill='{CARD}' stroke='{LINE}'/>")
        bx, hx, gx, y = 70, 210, 350, y0 + 56
        out.append(arrow(bx + 26, y, hx - 30, y, BAT))
        if sell:
            out.append(arrow(hx + 26, y, gx - 30, y, BAT, dashed=True))
            out.append(text((hx + gx) / 2, y - 12, t["sell"], 13, BAT, "middle"))
        else:
            out.append(f"<line x1='{hx + 36}' y1='{y - 13}' x2='{gx - 36}' y2='{y + 13}' stroke='{RED}' stroke-width='3'/>"
                       f"<line x1='{hx + 36}' y1='{y + 13}' x2='{gx - 36}' y2='{y - 13}' stroke='{RED}' stroke-width='3'/>")
        out += [node(bx, y, t["bat"], BAT, "▮"), node(hx, y, t["house"], HOUSE, "⌂"), node(gx, y, t["grid"], GRID, "⚡")]
        for k, line in enumerate(wrap(t[key], 44)):
            out.append(text(210, y0 + 126 + k * 19, line, 14, TXT, "middle"))
    return svg(W, top + 2 * 178 + 4, "\n".join(out), t["export_title"])


if __name__ == "__main__":
    for lang in ("sv", "en"):
        for name, fn in (("batteri-lagen", intents), ("batteri-stilar", styles), ("batteri-dygn", day),
                         ("batteri-salja", export)):
            (HERE / f"{name}-{lang}.svg").write_text(fn(lang), encoding="utf-8")
            print("skrev", f"{name}-{lang}.svg")
        for name, fn in (("batteri-lagen", intents_m), ("batteri-stilar", styles_m), ("batteri-dygn", day_m),
                         ("batteri-salja", export_m)):
            (HERE / f"{name}-{lang}-mobil.svg").write_text(fn(lang), encoding="utf-8")
            print("skrev", f"{name}-{lang}-mobil.svg")
