"""
AlphaCycle Historical Returns Calculator
Computes average forward returns by ARC zone from historical backtest data.
"""
from typing import Optional


def compute_historical_returns(backtest_data: list) -> dict:
    """
    Analyzes backtest data and computes average forward returns by ARC zone.

    backtest_data: List of dicts with date, arc_score (or score), btc_price (or price).

    Returns:
      zones, best_entry_zone, sample_events, data_points_used
    """
    if not backtest_data or len(backtest_data) < 10:
        return _empty_returns()

    # Normalize keys (backtest uses "score"/"price", we use arc_score/btc_price)
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

    zone_results = {
        "low": [],
        "moderate": [],
        "elevated": [],
        "extreme": [],
    }

    def get_zone(arc: float) -> str:
        if arc < 30:
            return "low"
        if arc < 60:
            return "moderate"
        if arc < 75:
            return "elevated"
        return "extreme"

    for i, entry in enumerate(data):
        arc = float(entry.get("arc_score", 50))
        price = float(entry.get("btc_price", 0))
        zone = get_zone(arc)

        def fwd_return(weeks: int) -> Optional[float]:
            target_i = i + weeks
            if target_i >= len(data):
                return None
            fwd_price = float(data[target_i].get("btc_price", 0))
            if fwd_price <= 0:
                return None
            return (fwd_price - price) / price * 100

        r3m = fwd_return(WEEKS_3M)
        r6m = fwd_return(WEEKS_6M)
        r12m = fwd_return(WEEKS_12M)

        zone_results[zone].append(
            {
                "date": entry.get("date", ""),
                "arc": round(arc, 1),
                "price": price,
                "r3m": r3m,
                "r6m": r6m,
                "r12m": r12m,
            }
        )

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

    zone_meta = {
        "low": "0-30",
        "moderate": "30-60",
        "elevated": "60-75",
        "extreme": "75-100",
    }

    zones_output = {}
    for zone, entries in zone_results.items():
        s3m = stats(entries, "r3m")
        s6m = stats(entries, "r6m")
        s12m = stats(entries, "r12m")
        zones_output[zone] = {
            "range": zone_meta[zone],
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
    for zone, entries in zone_results.items():
        for e in entries[-3:]:
            if e.get("r12m") is not None:
                sample_events.append(
                    {
                        "date": e["date"],
                        "arc": e["arc"],
                        "price": round(e["price"]),
                        "r12m": round(e["r12m"], 1),
                        "zone": zone,
                    }
                )

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

        results.append({
            "arc_range": label,
            "arc_min": lo,
            "arc_max": hi,
            "avg_3m_return": avg("r3m"),
            "avg_6m_return": avg("r6m"),
            "avg_12m_return": avg("r12m"),
            "sample_count": len(entries),
        })
    return results


def _empty_returns() -> dict:
    empty_zone = {
        "range": "N/A",
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
            "low": {**empty_zone, "range": "0-30"},
            "moderate": {**empty_zone, "range": "30-60"},
            "elevated": {**empty_zone, "range": "60-75"},
            "extreme": {**empty_zone, "range": "75-100"},
        },
        "best_entry_zone": None,
        "sample_events": [],
        "data_points_used": 0,
    }
