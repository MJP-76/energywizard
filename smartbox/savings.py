"""
savings.py - besparing per dag, för besparingskortet i webdashboard.

Samma formel som den publika sidan (scripts/export_public_stats.py) och HA-sensorn
sensor.smartbox_besparing_idag (ha_publisher.py), inte en ny definition:

    besparing = (dygnets snittpris - effektviktat snittpris vi faktiskt betalade) × köpt kWh

Alltså vad tajmningen sparade jämfört med om samma el köpts jämnt över dygnet. En dag då vi
köpte dyrare än snittet blir negativ och visas så, inte bortfiltrerad.

Skillnad mot den publika sidan: dygnen räknas i svensk tid (Europe/Stockholm), inte i
databasens UTC, så "idag" i kortet är samma dag som på klockan.

daily_rows() läser databasen; summarize_periods() är ren och testas i tests/test_savings.py.
"""

from sqlalchemy import text

_DAILY_SQL = text("""
    SELECT (timestamp AT TIME ZONE 'Europe/Stockholm')::date AS d,
           sum(net_power) / 60000.0 AS kwh,
           avg(price) AS day_avg,
           sum(net_power * price) / nullif(sum(net_power), 0) AS paid_avg
    FROM sensor_log
    WHERE net_power > 0 AND price IS NOT NULL
      AND timestamp >= now() - make_interval(days => :days)
    GROUP BY 1
    HAVING sum(net_power) > 0
    ORDER BY 1
""")


def daily_rows(conn, days=40):
    """[{day: 'YYYY-MM-DD', kwh, day_avg, paid_avg, saved_kr, would_cost_kr}] för de senaste dagarna."""
    out = []
    for d, kwh, day_avg, paid_avg in conn.execute(_DAILY_SQL, {"days": int(days)}).fetchall():
        row = build_day(d.isoformat(), kwh, day_avg, paid_avg)
        if row:
            out.append(row)
    return out


def build_day(day, kwh, day_avg, paid_avg):
    if kwh is None or day_avg is None or paid_avg is None:
        return None
    kwh, day_avg, paid_avg = float(kwh), float(day_avg), float(paid_avg)
    return {
        "day": day,
        "kwh": round(kwh, 2),
        "day_avg": round(day_avg, 4),
        "paid_avg": round(paid_avg, 4),
        "saved_kr": round((day_avg - paid_avg) * kwh, 2),
        "would_cost_kr": round(day_avg * kwh, 2),
    }


def _summary(rows):
    saved = sum(r["saved_kr"] for r in rows)
    would = sum(r["would_cost_kr"] for r in rows)
    kwh = sum(r["kwh"] for r in rows)
    return {
        "saved_kr": round(saved, 2),
        "kwh": round(kwh, 1),
        "paid_kr": round(would - saved, 2),
        # Procent av vad samma el hade kostat till snittpris. Bara meningsfullt när den
        # kostnaden är positiv (en minuspris-dag kan göra den negativ).
        "pct": round(100.0 * saved / would, 1) if would > 0.5 else None,
        "days": len(rows),
    }


def summarize_periods(rows, today):
    """rows från daily_rows(), today = 'YYYY-MM-DD' i svensk tid.

    today: bara dagens rad (kan saknas tidigt på morgonen). week: de 7 kalenderdagarna
    t.o.m. idag. month: innevarande kalendermånad. Dagar utan data räknas inte som noll-
    besparing, de räknas inte alls (days visar hur många som fanns)."""
    from datetime import date, timedelta
    t = date.fromisoformat(today)
    week_start = (t - timedelta(days=6)).isoformat()
    month_prefix = today[:7]
    rows = sorted(rows or [], key=lambda r: r["day"])
    return {
        "today": _summary([r for r in rows if r["day"] == today]),
        "week": _summary([r for r in rows if week_start <= r["day"] <= today]),
        "month": _summary([r for r in rows if r["day"].startswith(month_prefix) and r["day"] <= today]),
    }


# ---- Pengar per dag och period (Ekonomi-sidan) ---------------------------------------------------------------------
# Köpt och såld el minut för minut (sensor_log: en rad per minut, net_power + = köp), värderad med samma formel som
# motorn (nordpool.sql_buy_cost_expr/sql_sell_income_expr: moms, nätavgift, skatt och påslag enligt inställningarna).
def _money_sql():
    import nordpool
    buy, sell = nordpool.sql_buy_cost_expr("price", "timestamp"), nordpool.sql_sell_income_expr("price")
    return text(f"""
        SELECT (timestamp AT TIME ZONE 'Europe/Stockholm')::date AS d,
               sum(GREATEST(net_power, 0)) / 60000.0 AS bought_kwh,
               sum(GREATEST(net_power, 0) * {buy}) / 60000.0 AS cost,
               sum(GREATEST(-net_power, 0)) / 60000.0 AS sold_kwh,
               sum(GREATEST(-net_power, 0) * {sell}) / 60000.0 AS income
        FROM sensor_log
        WHERE net_power IS NOT NULL AND price IS NOT NULL AND timestamp >= now() - make_interval(days => :days)
        GROUP BY 1 ORDER BY 1""")


def money_rows(conn, days=40):
    """[{day, bought_kwh, cost, sold_kwh, income, net}] - kostnad och intäkt i landets valuta."""
    out = []
    for d, bk, cost, sk, inc in conn.execute(_money_sql(), {"days": int(days)}).fetchall():
        bk, cost, sk, inc = (float(x or 0) for x in (bk, cost, sk, inc))
        out.append({"day": d.isoformat(), "bought_kwh": round(bk, 2), "cost": round(cost, 2), "sold_kwh": round(sk, 2),
                    "income": round(inc, 2), "net": round(cost - inc, 2)})
    return out


def money_periods(rows, today):
    """Idag / 7 dagar / innevarande månad, samma perioder som summarize_periods()."""
    from datetime import date, timedelta
    t = date.fromisoformat(today)
    week_start = (t - timedelta(days=6)).isoformat()

    def tot(rs):
        s = {k: round(sum(r[k] for r in rs), 2) for k in ("bought_kwh", "cost", "sold_kwh", "income", "net")}
        s["avg_paid"] = round(s["cost"] / s["bought_kwh"], 3) if s["bought_kwh"] > 0.05 else None
        s["days"] = len(rs)
        return s
    rows = sorted(rows or [], key=lambda r: r["day"])
    return {"today": tot([r for r in rows if r["day"] == today]),
            "week": tot([r for r in rows if week_start <= r["day"] <= today]),
            "month": tot([r for r in rows if r["day"].startswith(today[:7]) and r["day"] <= today])}
