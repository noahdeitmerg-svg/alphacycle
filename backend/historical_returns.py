"""
AlphaCycle Historical Returns Calculator
Computes average forward returns by ARC zone from historical backtest data.
"""
from typing import Optional


def compute_historical_returns(backtest_data: list) -> dict:
    """
    Analyzes backtest data and computes average forward returns by ARC zone.
    Zone-crossing entry logic: an entry is counted ONLY when ARC crosses FROM
    OUTSIDE the zone INTO the zone (previous week not in zone, current week in zone).
    Forward return = (price at 52 weeks / entry price - 1) * 100.

    backtest_data: List of dicts with date, arc_score (or score), btc_price (or price).

    Returns:
      zones (entry_count, avg_12m, win_rate_12m, avg_3m, avg_6m, min_12m, max_12m),
      best_entry_zone, sample_events, data_points_used
    """
    if not backtest_data or len(backtest_data) < 10:
        return _empty_returns()

    def norm(d):
        return {
            "date": d.get("date", ""),
            "arc_score": d.get("arc_score") if d.get("arc_score") is not None else d.get("score"),
            "btc_price": d.get("btc_price") if d.get("btc_price") is not None else d.get("price"),
        }

    data = [norm(d) for d in backtest_data]
    data = sorted(data, key=lambda x: x.get("date", ""))

    data = [
        d
        for d in data
        if d.get("arc_score") is not None
        and d.get("btc_price") is not None
        and (d.get("btc_price") or 0) > 0
    ]

    if len(data) < 20:
        return _empty_returns()

    WEEKS_3M = 13
    WEEKS_6M = 26
    WEEKS_12M = 52

    def in_zone(arc: float, zone: str) -> bool:
        a = float(arc)
        if zone == "deep_value":
            return 0 <= a <= 29
        if zone == "accumulation":
            return 30 <= a <= 39
        if zone == "expansion":
            return 40 <= a <= 59
        if zone == "risk_rising":
            return 60 <= a <= 69
        if zone == "euphoria":
            return 70 <= a <= 100
        return False

    zone_entries = {
        "deep_value": [],
        "accumulation": [],
        "expansion": [],
        "risk_rising": [],
        "euphoria": [],
    }

    for i in range(1, len(data)):
        arc_curr = float(data[i].get("arc_score", 50))
        arc_prev = float(data[i - 1].get("arc_score", 50))
        price_curr = float(data[i].get("btc_price", 0))
        if price_curr <= 0:
            continue

        def fwd_return(weeks: int) -> Optional[float]:
            target_i = i + weeks
            if target_i >= len(data):
                return None
            fwd_price = float(data[target_i].get("btc_price", 0))
            if fwd_price <= 0:
                return None
            return (fwd_price - price_curr) / price_curr * 100

        for zone in zone_entries:
            if in_zone(arc_prev, zone) or not in_zone(arc_curr, zone):
                continue
            r3m = fwd_return(WEEKS_3M)
            r6m = fwd_return(WEEKS_6M)
            r12m = fwd_return(WEEKS_12M)
            zone_entries[zone].append({
                "date": data[i].get("date", ""),
                "arc": round(arc_curr, 1),
                "price": price_curr,
                "r3m": r3m,
                "r6m": r6m,
                "r12m": r12m,
            })

    zone_meta = {
        "deep_value": ("0-29", "Deep Value"),
        "accumulation": ("30-39", "Accumulation"),
        "expansion": ("40-59", "Expansion"),
        "risk_rising": ("60-69", "Risk Rising"),
        "euphoria": ("70-100", "Euphoria"),
    }

    def stats(entries: list, key: str) -> dict:
        vals = [e[key] for e in entries if e.get(key) is not None]
        if not vals:
            return {"avg": None, "min": None, "max": None, "win_rate": None, "count": 0}
        avg = sum(vals) / len(vals)
        wins = sum(1 for v in vals if v > 0)
        win_rate = wins / len(vals) * 100
        return {
            "avg": round(avg, 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
            "win_rate": round(win_rate, 1),
            "count": len(vals),
        }

    zones_output = {}
    for zone, entries in zone_entries.items():
        range_str, zone_name = zone_meta[zone]
        s3m = stats(entries, "r3m")
        s6m = stats(entries, "r6m")
        s12m = stats(entries, "r12m")
        zones_output[zone] = {
            "range": range_str,
            "zone_name": zone_name,
            "entry_count": len(entries),
            "avg_3m": s3m["avg"],
            "avg_6m": s6m["avg"],
            "avg_12m": s12m["avg"],
            "min_12m": s12m["min"],
            "max_12m": s12m["max"],
            "win_rate_12m": s12m["win_rate"],
        }

    best = max(
        zones_output.items(),
        key=lambda kv: (kv[1].get("avg_12m") or -999),
    )

    sample_events = []
    for zone, entries in zone_entries.items():
        for e in entries[-3:]:
            if e.get("r12m") is not None:
                sample_events.append({
                    "date": e["date"],
                    "arc": e["arc"],
                    "price": round(e["price"]),
                    "r12m": round(e["r12m"], 1),
                    "zone": zone,
                })

    return {
        "zones": zones_output,
        "best_entry_zone": best[0],
        "sample_events": sample_events[-10:],
        "data_points_used": len(data),
    }


def compute_arc_forward_returns(backtest_data: list) -> list:
    """
    Finer buckets: 0-25, 25-35, 35-50, 50-70, 70-85, 85-100.
    """
    def norm(d):
        return {
            "date": d.get("date", ""),
            "arc_score": d.get("arc_score") if d.get("arc_score") is not None else d.get("score"),
            "btc_price": d.get("btc_price") if d.get("btc_price") is not None else d.get("price"),
        }

    BUCKETS = [
        (0, 25, "0-25"),
        (25, 35, "25-35"),
        (35, 50, "35-50"),
        (50, 70, "50-70"),
        (70, 85, "70-85"),
        (85, 100, "85-100"),
    ]
    WEEKS_3M = 13
    WEEKS_6M = 26
    WEEKS_12M = 52

    data = [norm(d) for d in (backtest_data or [])]
    data = [d for d in data if d.get("arc_score") is not None and (d.get("btc_price") or 0) > 0]
    data = sorted(data, key=lambda x: x.get("date", ""))

    bucket_data = {b[2]: [] for b in BUCKETS}

    for i, entry in enumerate(data):
        arc = float(entry.get("arc_score", 50))
        price = float(entry.get("btc_price", 0))
        for lo, hi, label in BUCKETS:
            if lo <= arc < hi:
                def fwd(weeks):
                    ti = i + weeks
                    if ti >= len(data):
                        return None
                    fp = float(data[ti].get("btc_price", 0))
                    if fp <= 0:
                        return None
                    return (fp - price) / price * 100

                bucket_data[label].append({"r3m": fwd(WEEKS_3M), "r6m": fwd(WEEKS_6M), "r12m": fwd(WEEKS_12M)})
                break

    results = []
    for lo, hi, label in BUCKETS:
        entries = bucket_data[label]

        def avg(key):
            vals = [e[key] for e in entries if e.get(key) is not None]
            if not vals:
                return None
            return round(sum(vals) / len(vals), 1)

        r12_vals = [e.get("r12m") for e in entries if e.get("r12m") is not None]
        win_rate_12m = round(sum(1 for v in r12_vals if v > 0) / len(r12_vals) * 100, 1) if r12_vals else None

        results.append({
            "arc_range": label,
            "arc_min": lo,
            "arc_max": hi,
            "avg_3m_return": avg("r3m"),
            "avg_6m_return": avg("r6m"),
            "avg_12m_return": avg("r12m"),
            "sample_count": len(entries),
            "win_rate_12m": win_rate_12m,
        })
    return results


def compute_high_risk_drawdown(backtest_data: list) -> dict:
    """
    For Euphoria zone (ARC >= 70): zone-crossing entry only.
    Entry when ARC crosses FROM outside (prev < 70) INTO zone (curr >= 70).
    For each such entry: max drawdown from peak after entry within 52 weeks.
    Drawdown = (trough - peak) / peak * 100 (negative).
    Returns: avg_drawdown, max_drawdown (worst), min_drawdown (mildest), sample_count.
    """
    def norm(d):
        return {
            "date": d.get("date", ""),
            "arc_score": d.get("arc_score") if d.get("arc_score") is not None else d.get("score"),
            "btc_price": d.get("btc_price") if d.get("btc_price") is not None else d.get("price"),
        }

    data = [norm(d) for d in (backtest_data or [])]
    data = [d for d in data if d.get("arc_score") is not None and (d.get("btc_price") or 0) > 0]
    data = sorted(data, key=lambda x: x.get("date", ""))

    drawdowns = []
    for i in range(1, len(data)):
        arc_curr = float(data[i].get("arc_score", 0))
        arc_prev = float(data[i - 1].get("arc_score", 0))
        if arc_prev >= 70 or arc_curr < 70:
            continue
        entry_price = float(data[i].get("btc_price", 0))
        window_end = min(i + 52, len(data))
        window = data[i:window_end]
        prices_in_window = [float(d.get("btc_price", 0)) for d in window if d.get("btc_price")]

        if len(prices_in_window) >= 4:
            peak = max(prices_in_window)
            peak_idx = prices_in_window.index(peak)
            post_peak = prices_in_window[peak_idx:]
            if post_peak:
                trough = min(post_peak)
                if peak > 0:
                    dd = (trough - peak) / peak * 100
                    drawdowns.append(round(dd, 1))

    if not drawdowns:
        return {"avg_drawdown": None, "max_drawdown": None, "min_drawdown": None, "sample_count": 0}

    return {
        "avg_drawdown": round(sum(drawdowns) / len(drawdowns), 1),
        "max_drawdown": round(min(drawdowns), 1),
        "min_drawdown": round(max(drawdowns), 1),
        "sample_count": len(drawdowns),
    }


def _empty_returns() -> dict:
    empty_zone = {
        "range": "N/A",
        "zone_name": "",
        "entry_count": 0,
        "avg_3m": None,
        "avg_6m": None,
        "avg_12m": None,
        "min_12m": None,
        "max_12m": None,
        "win_rate_12m": None,
    }
    return {
        "zones": {
            "deep_value": {**empty_zone, "range": "0-29", "zone_name": "Deep Value"},
            "accumulation": {**empty_zone, "range": "30-39", "zone_name": "Accumulation"},
            "expansion": {**empty_zone, "range": "40-59", "zone_name": "Expansion"},
            "risk_rising": {**empty_zone, "range": "60-69", "zone_name": "Risk Rising"},
            "euphoria": {**empty_zone, "range": "70-100", "zone_name": "Euphoria"},
        },
        "best_entry_zone": None,
        "sample_events": [],
        "data_points_used": 0,
    }
