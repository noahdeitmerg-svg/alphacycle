#!/usr/bin/env python3
"""
Independent dashboard / ARC verification (Cowork 2026-06-04).

Pulls the LIVE production API and independently re-derives the numbers the
dashboard and landing page show, to catch overstated / wrong / fabricated
figures. Does NOT trust the backend's own historical-returns endpoint — it
recomputes zone forward-returns from the raw backtest series and compares.

Run:  python backend/scripts/verify_dashboard.py
"""
import json
import urllib.request
import bisect
from datetime import date

BASE = "https://alphacycle-production.up.railway.app"

ZONES = ["deep_value", "accumulation", "expansion", "risk_rising", "euphoria"]


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "alphacycle-verify"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def zone_of(a):
    if a < 30:
        return "deep_value"
    if a < 40:
        return "accumulation"
    if a < 60:
        return "expansion"
    if a < 70:
        return "risk_rising"
    return "euphoria"


def pct(a, b):
    return (a / b - 1.0) * 100.0 if b else float("nan")


def main():
    print("=" * 70)
    print("ALPHACYCLE INDEPENDENT VERIFICATION")
    print("=" * 70)

    arc = get("/api/arc-summary")
    bt = get("/api/backtest")["results"]
    hr = get("/api/historical-returns")["zones"]

    print(f"\nLive ARC: {arc.get('arc_score')}  zone={arc.get('zone_name')}  "
          f"btc={arc.get('btc_price')}  decision={arc.get('decision')}")
    print(f"Backtest points: {len(bt)}  range {bt[0]['date']} -> {bt[-1]['date']}")

    # ---- 1. DATA INTEGRITY ------------------------------------------------
    print("\n[1] DATA INTEGRITY")
    issues = []
    prev = None
    for r in bt:
        d, p, a = r["date"], r.get("price"), r.get("arc_score")
        if p is None or p <= 0:
            issues.append(f"bad price {d}: {p}")
        if a is None or a < 0 or a > 100:
            issues.append(f"arc out of range {d}: {a}")
        hi, lo = r.get("high"), r.get("low")
        if hi is not None and lo is not None and hi < lo:
            issues.append(f"high<low {d}")
        if prev is not None and d <= prev:
            issues.append(f"date not increasing at {d}")
        prev = d
    print(f"    checked {len(bt)} rows; issues: {len(issues)}")
    for x in issues[:10]:
        print("    !", x)

    # ---- 2. LIVE ARC vs BACKTEST LAST -------------------------------------
    print("\n[2] LIVE ARC vs BACKTEST LAST POINT")
    live = float(arc.get("arc_score"))
    last = float(bt[-1]["arc_score"])
    print(f"    live={live}  backtest_last={last}  diff={abs(live-last):.2f}  "
          f"{'OK' if abs(live-last) < 1.5 else 'MISMATCH'}")

    # ---- 3. ZONE BOUNDARY CONSISTENCY -------------------------------------
    print("\n[3] LIVE ZONE NAME vs BOUNDARY RULE")
    api_zone = (arc.get("zone_name") or "").lower().replace(" ", "_")
    calc_zone = zone_of(live)
    print(f"    api={api_zone}  calc={calc_zone}  "
          f"{'OK' if api_zone == calc_zone else 'MISMATCH'}")

    # ---- 4. INDEPENDENT ZONE FORWARD-RETURN BACKTEST ----------------------
    # Entry on zone-crossing; 365 calendar-day forward BTC return.
    print("\n[4] INDEPENDENT ZONE FORWARD RETURNS (recomputed from raw series)")
    dates = [date.fromisoformat(r["date"][:10]) for r in bt]
    ords = [d.toordinal() for d in dates]
    prices = [float(r["price"]) for r in bt]

    def price_on_or_after(target_ord):
        j = bisect.bisect_left(ords, target_ord)
        return prices[j] if j < len(ords) else None

    entries = {z: [] for z in ZONES}
    prevz = None
    for i, r in enumerate(bt):
        z = zone_of(float(r["arc_score"]))
        if z != prevz:
            fp = price_on_or_after(ords[i] + 365)
            if fp is not None:
                entries[z].append(pct(fp, prices[i]))
            prevz = z

    print(f"    {'zone':<13}{'mine_n':>7}{'mine_avg12m':>13}{'mine_win':>10}"
          f"{'api_n':>7}{'api_avg12m':>12}{'api_win':>9}  flag")
    for z in ZONES:
        mine = entries[z]
        mn = len(mine)
        mavg = sum(mine) / mn if mn else float("nan")
        mwin = 100.0 * sum(1 for x in mine if x > 0) / mn if mn else float("nan")
        a = hr.get(z, {})
        aavg = a.get("avg_12m")
        awin = a.get("win_rate_12m")
        an = a.get("entry_count")
        flag = ""
        if aavg is not None and mn:
            if abs(mavg - aavg) > max(25.0, 0.25 * abs(aavg)):
                flag = "<<< CHECK avg"
        mavg_s = f"{mavg:9.1f}" if mn else "   n/a   "
        mwin_s = f"{mwin:8.0f}" if mn else "  n/a   "
        aavg_s = f"{aavg:10.1f}" if isinstance(aavg, (int, float)) else "    n/a   "
        awin_s = f"{awin:7.0f}" if isinstance(awin, (int, float)) else "  n/a  "
        print(f"    {z:<13}{mn:>7}{mavg_s:>13}{mwin_s:>10}{str(an):>7}{aavg_s:>12}{awin_s:>9}  {flag}")

    # ---- 5. LANDING / TRACK-RECORD HARDCODED CLAIMS vs DATA ---------------
    print("\n[5] HARDCODED LANDING CLAIMS vs BACKTEST DATA")
    idx = {r["date"][:10]: r for r in bt}

    def nearest(target_iso):
        t = date.fromisoformat(target_iso).toordinal()
        j = bisect.bisect_left(ords, t)
        j = min(max(j, 0), len(bt) - 1)
        return bt[j]

    def fwd12(target_iso):
        t = date.fromisoformat(target_iso).toordinal()
        i = min(bisect.bisect_left(ords, t), len(bt) - 1)
        fp = price_on_or_after(ords[i] + 365)
        return pct(fp, prices[i]) if fp else None

    for label, iso in [("Dec 2022 (claim ARC~12 BTC~16.5k +170%)", "2022-12-15"),
                       ("Oct 2024 (claim ARC~65 BTC~65k)", "2024-10-15")]:
        row = nearest(iso)
        f12 = fwd12(iso)
        f12s = f"{f12:.0f}%" if f12 is not None else "n/a (in future)"
        print(f"    {label}")
        print(f"        actual: date={row['date'][:10]} arc={row['arc_score']:.1f} "
              f"btc=${row['price']:,.0f}  fwd12m={f12s}")

    # all-time high check (for drawdown sanity)
    ath = max(prices)
    ath_date = bt[prices.index(ath)]["date"][:10]
    print(f"\n    series ATH: ${ath:,.0f} on {ath_date}  (current ${prices[-1]:,.0f}, "
          f"{pct(prices[-1], ath):.0f}% from ATH)")

    print("\n" + "=" * 70)
    print("DONE. Review [4] flags and [5] claims for overstatement.")
    print("=" * 70)


if __name__ == "__main__":
    main()
