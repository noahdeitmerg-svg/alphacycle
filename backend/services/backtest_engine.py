"""
backtest_engine.py - Alpha Cycle Intelligence v3.0

Authoritative daily ARC history: run_daily_backtest_full() + /tmp/daily_full_cache.json.
ARC uses arc_config.ARC_WEIGHTS: trend*ma_200w + drawdown*dd + liquidity*macro_liq + sentiment*fg_to_score(fear_greed) (v1.2: 0.35/0.30/0.15/0.20).
macro_liq from FRED Net Liquidity (WALCL - TGA - RRP) when available.
Return: [{"date": "YYYY-MM-DD", "price": float (close), "high": float, "low": float, "score": float}, ...]
"""

import asyncio
import csv
import json
import logging
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# 5-zone buckets (lo inclusive, hi exclusive) — aligned with arc_config.ARC_ZONES / get_zone_name
ZONES = [(0, 30), (30, 40), (40, 60), (60, 70), (70, 101)]
ZONE_NAMES = ["Deep Value", "Accumulation", "Expansion", "Risk Rising", "Euphoria"]

try:
    from scoring import drawdown_score_hl, ma_deviation_score, safe_float, fg_to_score, arc_display_score
    from arc_config import ARC_WEIGHTS
except ImportError:  # pragma: no cover
    from backend.scoring import drawdown_score_hl, ma_deviation_score, safe_float, fg_to_score, arc_display_score
    from backend.arc_config import ARC_WEIGHTS


HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
WINDOW_200W = 200  # 200 weekly data points = 200-week MA (daily [::7] slice in run_daily_backtest_full)
DAILY_CACHE_FILE = Path("/tmp/daily_full_cache.json")
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "btc_daily_kraken.csv"
# Bump when daily merge or daily-ARC methodology changes; stale files rebuild on next load.
DAILY_PRICE_CACHE_EPOCH = "20260412-arc-v1.2-weights"


def _load_csv_history() -> List[Dict[str, Any]]:
    """Load static Kraken BTC/USD daily OHLC from bundled CSV (2013-10-06 to 2023-12-31)."""
    if not CSV_PATH.exists():
        logger.warning("CSV not found at %s", CSV_PATH)
        return []
    out = []
    try:
        with open(CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = int(row["timestamp"])
                    close = float(row["close"])
                    high = float(row["high"])
                    low = float(row["low"])
                    if close > 0:
                        dt = datetime.utcfromtimestamp(ts).date().isoformat()
                        out.append({"date": dt, "price": close, "high": high, "low": low})
                except (KeyError, ValueError, TypeError):
                    continue
        logger.info(
            "CSV loaded: %s daily candles (%s to %s)",
            len(out),
            out[0]["date"] if out else "?",
            out[-1]["date"] if out else "?",
        )
    except Exception as e:
        logger.error("CSV load failed: %s", e)
    return sorted(out, key=lambda x: x["date"]) if out else []


async def _fetch_gap_from_cryptocompare(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Fetch daily BTC/USD candles from CryptoCompare (Kraken exchange) for a specific date range."""
    try:
        start_ts = int(datetime.fromisoformat(start_date).timestamp())
        end_ts = int(datetime.fromisoformat(end_date).timestamp())
        days_needed = (end_ts - start_ts) // 86400 + 1

        params = {
            "fsym": "BTC",
            "tsym": "USD",
            "limit": min(days_needed, 2000),
            "toTs": end_ts,
            "e": "Kraken",
        }
        if os.environ.get("CRYPTOCOMPARE_KEY"):
            params["api_key"] = os.environ["CRYPTOCOMPARE_KEY"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://min-api.cryptocompare.com/data/v2/histoday",
                params=params,
            )
            data = resp.json()

        if data.get("Response") != "Success" or "Data" not in data:
            logger.warning("CryptoCompare gap fetch failed: %s", data.get("Message", "unknown"))
            return []

        entries = data.get("Data", {}).get("Data", [])
        out = []
        for entry in entries:
            try:
                ts = int(entry["time"])
                close = float(entry["close"])
                high = float(entry["high"])
                low = float(entry["low"])
                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                if close > 0 and dt >= start_date and dt <= end_date:
                    out.append({"date": dt, "price": close, "high": high, "low": low})
            except (KeyError, ValueError, TypeError):
                continue

        logger.info(
            "CryptoCompare gap fill: %s candles (%s to %s)",
            len(out),
            out[0]["date"] if out else "?",
            out[-1]["date"] if out else "?",
        )
        return out
    except Exception as e:
        logger.warning("CryptoCompare gap fetch error: %s", e)
        return []


async def _fetch_btc_daily_full() -> List[Dict[str, Any]]:
    """
    DISABLED — Kraken daily OHLC API only returns ~720 most recent candles.
    Pagination does not retrieve historical data beyond that window.
    Replaced by CSV-based loading in _load_or_build_daily_cache().
    """
    logger.warning("_fetch_btc_daily_full() is disabled — use CSV-based cache loader")
    return []


async def _load_or_build_daily_cache() -> List[Dict[str, Any]]:
    """
    Build complete daily BTC price history from three sources:
    1. Static CSV: Kraken official OHLC 2013-10-06 to 2023-12-31
    2. Gap bridge: CryptoCompare e=Kraken for any gap between CSV and API
    3. Kraken live API: most recent ~720 daily candles

    Result is cached in /tmp/daily_full_cache.json with incremental updates.
    """
    today = datetime.utcnow().date().isoformat()

    # Try file cache first (wrapped dict with epoch; legacy bare list is discarded once)
    if DAILY_CACHE_FILE.exists():
        try:
            raw = json.loads(DAILY_CACHE_FILE.read_text())
            cached: Optional[List[Dict[str, Any]]] = None
            if isinstance(raw, list):
                logger.info(
                    "Daily cache legacy format (bare list): removing for epoch %s",
                    DAILY_PRICE_CACHE_EPOCH,
                )
                try:
                    DAILY_CACHE_FILE.unlink()
                except OSError:
                    pass
            elif isinstance(raw, dict) and isinstance(raw.get("daily_bars"), list):
                if raw.get("epoch") != DAILY_PRICE_CACHE_EPOCH:
                    logger.info(
                        "Daily cache epoch mismatch (%s != %s): removing file",
                        raw.get("epoch"),
                        DAILY_PRICE_CACHE_EPOCH,
                    )
                    try:
                        DAILY_CACHE_FILE.unlink()
                    except OSError:
                        pass
                else:
                    cached = raw["daily_bars"]
            else:
                logger.warning("Daily cache unknown shape: removing file")
                try:
                    DAILY_CACHE_FILE.unlink()
                except OSError:
                    pass

            if cached and isinstance(cached, list) and len(cached) > 2000:
                last_date = cached[-1]["date"]
                if last_date >= today:
                    return cached
                # Drop last entry (may be incomplete) and fetch incremental update
                cached = cached[:-1]
                since_ts = int(datetime.fromisoformat(cached[-1]["date"]).timestamp())
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                    resp = await client.get(
                        "https://api.kraken.com/0/public/OHLC",
                        params={"pair": "XBTUSD", "interval": 1440, "since": since_ts},
                    )
                    data = resp.json()
                if not data.get("error") and "result" in data:
                    keys = [k for k in data["result"] if k != "last"]
                    if keys:
                        for c in data["result"][keys[0]]:
                            try:
                                close = float(c[4])
                                high = float(c[2])
                                low = float(c[3])
                                if close > 0:
                                    dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                                    cached.append({"date": dt, "price": close, "high": high, "low": low})
                            except (IndexError, TypeError, ValueError):
                                continue
                # Dedupe and sort
                seen = set()
                deduped = []
                for item in cached:
                    if item["date"] not in seen:
                        seen.add(item["date"])
                        deduped.append(item)
                cached = sorted(deduped, key=lambda x: x["date"])
                payload = {"epoch": DAILY_PRICE_CACHE_EPOCH, "daily_bars": cached}
                DAILY_CACHE_FILE.write_text(json.dumps(payload))
                logger.info("Daily cache incremental update: %s points to %s", len(cached), cached[-1]["date"])
                return cached
        except Exception as e:
            logger.warning("Daily cache load failed, rebuilding: %s", e)

    # === FULL REBUILD ===

    # 1. Load static CSV (2013 to 2023)
    csv_data = _load_csv_history()
    if not csv_data:
        logger.error("CSV history empty — cannot build daily cache")
        return []
    csv_end_date = csv_data[-1]["date"]
    logger.info("CSV base loaded: %s points, ends %s", len(csv_data), csv_end_date)

    # 2. Fetch Kraken API (recent ~720 days)
    since_ts = int(datetime.utcnow().timestamp()) - 750 * 86400
    kraken_recent: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": "XBTUSD", "interval": 1440, "since": since_ts},
            )
            data = resp.json()
        if not data.get("error") and "result" in data:
            keys = [k for k in data["result"] if k != "last"]
            if keys:
                for c in data["result"][keys[0]]:
                    try:
                        close = float(c[4])
                        high = float(c[2])
                        low = float(c[3])
                        if close > 0:
                            dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                            kraken_recent.append({"date": dt, "price": close, "high": high, "low": low})
                    except (IndexError, TypeError, ValueError):
                        continue
        logger.info(
            "Kraken API recent: %s points (%s to %s)",
            len(kraken_recent),
            kraken_recent[0]["date"] if kraken_recent else "?",
            kraken_recent[-1]["date"] if kraken_recent else "?",
        )
    except Exception as e:
        logger.warning("Kraken API fetch failed: %s", e)

    # 3. Detect and bridge gap
    api_start_date = kraken_recent[0]["date"] if kraken_recent else today
    gap_data: List[Dict[str, Any]] = []

    if csv_end_date < api_start_date:
        gap_start = (datetime.fromisoformat(csv_end_date) + timedelta(days=1)).date().isoformat()
        gap_end = (datetime.fromisoformat(api_start_date) - timedelta(days=1)).date().isoformat()
        gap_days = (datetime.fromisoformat(gap_end) - datetime.fromisoformat(gap_start)).days + 1

        if gap_days > 0:
            logger.info(
                "Gap detected: %s to %s (%s days) — fetching from CryptoCompare",
                gap_start,
                gap_end,
                gap_days,
            )
            gap_data = await _fetch_gap_from_cryptocompare(gap_start, gap_end)
            if not gap_data:
                logger.warning("Gap bridge failed — %s days will be missing", gap_days)

    # 4. Merge all three sources
    all_data = csv_data + gap_data + kraken_recent

    # Dedupe by date (later entries override earlier for overlapping dates)
    by_date: Dict[str, Dict[str, Any]] = {}
    for item in all_data:
        by_date[item["date"]] = item
    merged = sorted(by_date.values(), key=lambda x: x["date"])

    # 5. Save to file cache
    if merged:
        try:
            DAILY_CACHE_FILE.write_text(
                json.dumps({"epoch": DAILY_PRICE_CACHE_EPOCH, "daily_bars": merged})
            )
        except Exception:
            pass
        logger.info(
            "Daily cache built: %s points (%s to %s)",
            len(merged),
            merged[0]["date"],
            merged[-1]["date"],
        )

    return merged


async def _fetch_fred(series_id: str) -> list:
    """Fetch FRED series observations from 2013-01-01. Returns [{"t": ms, "v": float}, ...]."""
    FRED_KEY = os.getenv("FRED_API_KEY", "")
    if not FRED_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": FRED_KEY,
                    "file_type": "json",
                    "observation_start": "2013-01-01",
                },
            )
            data = r.json()
        return [
            {
                "t": int(datetime.strptime(o["date"], "%Y-%m-%d").timestamp()) * 1000,
                "v": float(o["value"]),
            }
            for o in data.get("observations", [])
            if o.get("value", ".") != "."
        ]
    except Exception:
        return []


def _get_net_liq_impulse_score(date_str: str, net_liq_by_date: Dict[str, float]) -> float:
    """Net Liq impulse score matching compute_arc_score() methodology.
    Uses 30d + 90d change with coefficients 2.5 and 1.5."""
    available = sorted([(d, v) for d, v in net_liq_by_date.items() if d <= date_str])
    if len(available) < 22:
        return 50.0
    cur = available[-1][1]
    prev_30d = available[-22][1]
    prev_90d = available[-65][1] if len(available) >= 65 else available[0][1]
    change_30d = (cur - prev_30d) / abs(prev_30d) * 100 if prev_30d != 0 else 0.0
    change_90d = (cur - prev_90d) / abs(prev_90d) * 100 if prev_90d != 0 else 0.0
    impulse = 50.0 - change_30d * 2.5 - change_90d * 1.5
    return max(0.0, min(100.0, impulse))


async def _fetch_fg_history() -> Dict[str, float]:
    """Fetch full F&G history from Alternative.me. Returns {date_str: value}."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                "https://api.alternative.me/fng/",
                params={"limit": 0, "format": "json"},
            )
            data = r.json()
        result: Dict[str, float] = {}
        for item in data.get("data", []):
            try:
                dt = datetime.utcfromtimestamp(int(item["timestamp"])).date().isoformat()
                result[dt] = float(item["value"])
            except Exception:
                continue
        logger.info("F&G history: %s pts", len(result))
        return result
    except Exception as e:
        logger.warning("F&G history failed: %s", e)
        return {}


def _rsi_to_fg(prices_so_far: List[float]) -> float:
    """
    Derive F&G proxy from RSI when real data unavailable.
    Uses RSI on weekly prices; returns 0-100 where low RSI ~ fear, high RSI ~ greed.
    """
    if len(prices_so_far) < 15:
        return 50.0
    try:
        deltas = [prices_so_far[i] - prices_so_far[i - 1] for i in range(1, len(prices_so_far))]
        period = 14
        gains = [max(0.0, d) for d in deltas[-period:]]
        losses = [max(0.0, -d) for d in deltas[-period:]]
        ag = sum(gains) / len(gains) if gains else 0.0
        al = sum(losses) / len(losses) if losses else 0.0
        if al == 0:
            rsi = 100.0 if ag > 0 else 50.0
        else:
            rsi = 100 - (100 / (1 + ag / al))
        rsi = max(0.0, min(100.0, rsi))
        return rsi
    except Exception:
        return 50.0


async def run_daily_backtest_full() -> Dict[str, Any]:
    """
    Full-range daily ARC backtest from ~2017 to today.

    METHODOLOGY: MA200w is computed from daily prices via [::7] slicing then
    moving_average(..., 200), replicating the exact pattern in compute_btc_score()
    (scoring.py L325-326). This is a deliberate methodology-alignment choice.
    [::7] daily != true weekly closes, but it ensures backtest and live ARC
    use identical methodology.
    """
    try:
        history = await _load_or_build_daily_cache()
    except Exception as e:
        return {"results": [], "error": f"Daily fetch failed: {e!s}"}

    if not history or len(history) < 1400:
        logger.error(
            "Backtest failed - insufficient daily history (points=%s)",
            len(history) if history else 0,
        )
        return {"results": [], "error": "insufficient daily history"}

    walcl_raw, tga_raw, rrp_raw, fg_history = await asyncio.gather(
        _fetch_fred("WALCL"),
        _fetch_fred("WTREGEN"),
        _fetch_fred("RRPONTSYD"),
        _fetch_fg_history(),
    )

    tga_dict = {item["t"]: item["v"] for item in tga_raw}
    rrp_dict = {item["t"]: item["v"] for item in rrp_raw}
    net_liq_by_date: Dict[str, float] = {}
    for item in walcl_raw:
        t = item["t"]
        w = float(item.get("v", 0))
        if w <= 0:
            continue
        tga_val = 0.0
        rrp_val = 0.0
        for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
            if t + delta in tga_dict:
                tga_val = tga_dict[t + delta]
                break
        for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
            if t + delta in rrp_dict:
                rrp_val = float(rrp_dict[t + delta]) * 1000
                break
        net = w - tga_val - rrp_val
        date_str = datetime.utcfromtimestamp(t // 1000).date().isoformat()
        net_liq_by_date[date_str] = net

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]

    DAILY_PER_WEEK = 7
    MIN_DAYS_FOR_MA200W = WINDOW_200W * DAILY_PER_WEEK

    fg_dates_sorted = sorted(fg_history.keys())

    def _fg_forward_fill(target_date: str) -> float:
        best = None
        for d in fg_dates_sorted:
            if d <= target_date:
                best = fg_history[d]
            else:
                break
        return best if best is not None else 50.0

    results: List[Dict[str, Any]] = []

    try:
        for idx, item in enumerate(history):
            price = prices[idx]
            if price <= 0:
                continue
            if idx + 1 < MIN_DAYS_FOR_MA200W:
                continue

            daily_up_to_now = prices[: idx + 1]
            weekly_sampled = daily_up_to_now[::DAILY_PER_WEEK]
            if len(weekly_sampled) < WINDOW_200W:
                continue
            ma_200w = sum(weekly_sampled[-WINDOW_200W:]) / WINDOW_200W
            if not math.isfinite(ma_200w) or ma_200w <= 0:
                continue

            daily_high = safe_float(item.get("high", price), price)
            daily_low = safe_float(item.get("low", price), price)

            ma_200w_score = ma_deviation_score(daily_high, ma_200w)

            prices_so_far = prices[: idx + 1]
            dd_score = drawdown_score_hl(prices_so_far, daily_low) if len(prices_so_far) >= 10 else 50.0

            if item["date"] in fg_history:
                fear_greed_raw = fg_history[item["date"]]
            else:
                fg_raw_ff = _fg_forward_fill(item["date"])
                fear_greed_raw = fg_raw_ff if fg_raw_ff != 50.0 else _rsi_to_fg(prices_so_far)
            fg_score = fg_to_score(fear_greed_raw)

            macro_liq = _get_net_liq_impulse_score(item["date"], net_liq_by_date)

            arc = (
                ma_200w_score * ARC_WEIGHTS["trend"]
                + dd_score * ARC_WEIGHTS["drawdown"]
                + macro_liq * ARC_WEIGHTS["liquidity"]
                + fg_score * ARC_WEIGHTS["sentiment"]
            )
            # Extreme Condition Boost - identical to compute_arc_score() in scoring.py
            if ma_200w_score > 78 and fg_score > 82:
                arc += 7.0
            elif ma_200w_score > 72 and fg_score > 75:
                arc += 3.0
            if dd_score < 18 and fg_score < 15:
                arc -= 7.0
            elif dd_score < 25 and fg_score < 20:
                arc -= 3.0
            arc = max(0.0, min(100.0, arc))

            results.append({
                "date": item["date"],
                "price": round(price, 2),
                "high": round(daily_high, 2),
                "low": round(daily_low, 2),
                "score": round(arc, 2),
                "score_display": round(arc_display_score(arc), 2),
                "c_trend": round(ma_200w_score, 2),
                "c_drawdown": round(dd_score, 2),
                "c_sentiment": round(fg_score, 2),
                "c_liquidity": round(macro_liq, 2),
            })

    except Exception as e:
        return {"results": results, "error": f"Daily backtest loop: {e!s}"}

    weekly_backtest_scores: Dict[str, float] = {}

    for ref_date in ["2022-11-21", "2024-03-14", "2025-01-20"]:
        daily_score = None
        for r in results:
            if r["date"] == ref_date:
                daily_score = r["score"]
                break
        weekly_score = weekly_backtest_scores.get(ref_date)
        delta = round(daily_score - weekly_score, 2) if (daily_score is not None and weekly_score is not None) else None
        logger.debug(
            "ARC VALIDATION: %s -> daily=%.1f weekly=%.1f delta=%s",
            ref_date,
            daily_score if daily_score is not None else -1,
            weekly_score if weekly_score is not None else -1,
            f"{delta:+.1f}" if delta is not None else "n/a",
        )

    logger.info(
        "Daily full backtest: %s points, range %s -> %s",
        len(results),
        results[0]["date"] if results else "?",
        results[-1]["date"] if results else "?",
    )
    return {"results": results}


__all__ = ["run_daily_backtest_full"]
