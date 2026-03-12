"""
backtest_engine.py - Alpha Cycle Intelligence v3.0

Historical backtest: file cache /tmp/backtest_cache.json.
Once loaded, only missing days (1-2) fetched. ARC = ma_200w*0.35 + drawdown*0.25 + macro_liq*0.25 + fg_to_score(fear_greed)*0.15.
macro_liq from FRED Net Liquidity (WALCL - TGA - RRP) when available.
Return: [{"date": "YYYY-MM-DD", "price": float (close), "high": float, "low": float, "score": float}, ...]
"""

import asyncio
import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# 5-zone buckets for historical returns (aligned with phaseOf / get_zone_name)
ZONES = [(0, 29), (30, 39), (40, 59), (60, 69), (70, 100)]
ZONE_NAMES = ["Deep Value", "Accumulation", "Expansion", "Risk Rising", "Euphoria"]

try:
    from scoring import drawdown_score, drawdown_score_hl, ma_deviation_score, safe_float, fg_to_score, arc_display_score
except ImportError:  # pragma: no cover
    from backend.scoring import drawdown_score, drawdown_score_hl, ma_deviation_score, safe_float, fg_to_score, arc_display_score


HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
WINDOW_200W = 200  # 200 wöchentliche Datenpunkte = 200-Wochen MA
CACHE_FILE = Path("/tmp/backtest_cache.json")


async def _fetch_since(since_ts: int) -> List[Dict[str, Any]]:
    """Fetch only new candles since given timestamp."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": "XBTUSD", "interval": 10080, "since": since_ts},
        )
        data = resp.json()
    if data.get("error") or "result" not in data:
        return []
    keys = [k for k in data["result"] if k != "last"]
    if not keys:
        return []
    out = []
    for c in data["result"][keys[0]]:
        try:
            close = float(c[4])
            high = float(c[2])
            low = float(c[3])
            if close > 0:
                dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                out.append({"date": dt, "price": close, "high": high, "low": low})
        except (IndexError, TypeError, ValueError):
            continue
    return out


async def _load_or_build_cache() -> List[Dict[str, Any]]:
    """Load from file cache or build from scratch."""
    today = datetime.utcnow().date().isoformat()

    if CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            if cached and isinstance(cached, list):
                if len(cached) < 400:  # expect ~720 weekly candles
                    try:
                        CACHE_FILE.unlink()
                    except Exception:
                        pass
                    raise Exception("cache too short, refetch")
                last_date = cached[-1]["date"]
                if last_date >= today:
                    return cached
                since_ts = int(datetime.fromisoformat(last_date).timestamp())
                new_candles = await _fetch_since(since_ts)
                if new_candles:
                    cached.extend(new_candles)
                    seen = set()
                    deduped = []
                    for item in cached:
                        if item["date"] not in seen:
                            seen.add(item["date"])
                            deduped.append(item)
                    cached = sorted(deduped, key=lambda x: x["date"])
                CACHE_FILE.write_text(json.dumps(cached))
                return cached
        except Exception as e:
            logger.warning("backtest cache load failed: %s", e)

    history = await _fetch_btc_history()
    if history:
        try:
            CACHE_FILE.write_text(json.dumps(history))
        except Exception:
            pass
    return history


async def _fetch_btc_history() -> List[Dict[str, Any]]:
    """Kraken OHLC weekly (interval=10080). 720 weeks = ~13.8y. since=2013-10-10. ARC chart ~10y from ~2014."""
    import time as _time
    since = 1381363200  # 2013-10-10, Kraken BTC live
    all_candles: List[list] = []

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        while True:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": "XBTUSD", "interval": 10080, "since": since},
            )
            data = resp.json()
            if data.get("error") or "result" not in data:
                logger.warning(
                    "Kraken OHLC error: %s since=%s",
                    data.get("error"),
                    since,
                )
                break
            keys = [k for k in data["result"] if k != "last"]
            if not keys:
                break
            candles = data["result"][keys[0]]
            if not candles:
                break
            all_candles.extend(candles)
            last = data["result"].get("last", 0)
            if last <= since or len(candles) < 10:
                break
            since = last
            await asyncio.sleep(1.2)

    out = []
    seen = set()
    for c in all_candles:
        try:
            ts = int(c[0])
            if ts in seen:
                continue
            seen.add(ts)
            close = float(c[4])
            high = float(c[2])
            low = float(c[3])
            if close > 0:
                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                out.append({"date": dt, "price": close, "high": high, "low": low})
        except (IndexError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["date"])


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


def _get_net_liq_score(date_str: str, net_liq_by_date: Dict[str, float], history_so_far: List[float]) -> float:
    """Net Liq 52w trend score for date_str. Returns 0-100; 50 if not enough data."""
    available = [(d, v) for d, v in net_liq_by_date.items() if d <= date_str]
    if len(available) < 2:
        return 50.0
    available.sort()
    cur = available[-1][1]
    prev_idx = max(0, len(available) - 53)
    prev = available[prev_idx][1]
    if prev == 0:
        return 50.0
    pct = (cur - prev) / abs(prev) * 100
    return max(0.0, min(100.0, 50 - pct * 2.0))


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


async def run_backtest() -> Dict[str, Any]:
    """
    Run historical backtest. Returns {"results": [{"date", "price", "score"}, ...], "error": "..."} on failure.
    """
    try:
        history = await _load_or_build_cache()
    except Exception as e:
        return {"results": [], "error": f"Fetch failed: {e!s}"}
    if not history:
        return {"results": [], "error": "No price history from API"}

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
                # FRED RRPONTSYD in billions; WALCL/TGA in millions
                rrp_val = float(rrp_dict[t + delta]) * 1000
                break
        net = w - tga_val - rrp_val
        date_str = datetime.utcfromtimestamp(t // 1000).date().isoformat()
        net_liq_by_date[date_str] = net

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]
    results: List[Dict[str, Any]] = []

    try:
        for idx, item in enumerate(history):
            price = prices[idx]
            if price <= 0:
                continue
            if idx + 1 < WINDOW_200W:
                continue
            window_prices = prices[idx + 1 - WINDOW_200W : idx + 1]
            if not window_prices:
                continue
            ma_200w = sum(window_prices) / len(window_prices)
            if not math.isfinite(ma_200w) or ma_200w <= 0:
                continue
            weekly_high = safe_float(history[idx].get("high", price), price)
            weekly_low = safe_float(history[idx].get("low", price), price)
            ma_200w_score = ma_deviation_score(weekly_high, ma_200w)
            prices_so_far = prices[: idx + 1]
            dd_score = drawdown_score_hl(prices_so_far, weekly_low)

            # F&G: echte Daten wenn vorhanden, sonst RSI-Proxy auf Weekly-Preisen
            if item["date"] in fg_history:
                fear_greed_raw = fg_history[item["date"]]
            else:
                fear_greed_raw = _rsi_to_fg(prices_so_far)
            fg_score = fg_to_score(fear_greed_raw)

            macro_liq = _get_net_liq_score(item["date"], net_liq_by_date, prices_so_far)
            arc = (
                ma_200w_score * 0.35
                + dd_score * 0.25
                + macro_liq * 0.25
                + fg_score * 0.15
            )
            arc = max(0.0, min(100.0, arc))

            results.append(
                {
                    "date": item["date"],
                    "price": round(price, 2),
                    "high": round(weekly_high, 2),
                    "low": round(weekly_low, 2),
                    "score": round(arc, 2),
                    "score_display": round(arc_display_score(arc), 2),
                }
            )
    except Exception as e:
        return {"results": results, "error": f"Backtest loop: {e!s}"}

    return {"results": results}


async def run_daily_backtest(days: int = 400) -> Dict[str, Any]:
    """
    Compute REAL daily ARC scores for the last `days` days.
    Uses daily Kraken candles (interval=1440), weekly MA200w from backtest,
    daily Fear & Greed, and forward-filled FRED net liquidity. No interpolation.
    """
    try:
        import time as _time

        # 1. Fetch daily candles from Kraken (interval=1440 = daily)
        since_ts = int(_time.time()) - (days + 30) * 86400  # buffer for MA/drawdown
        daily_candles: List[Dict[str, Any]] = []

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
                            ts = int(c[0])
                            close = float(c[4])
                            if close > 0:
                                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                                daily_candles.append({"date": dt, "price": close})
                        except (IndexError, TypeError, ValueError):
                            continue

        if len(daily_candles) < 30:
            return {"results": [], "error": "insufficient daily candles"}

        # Sort and dedupe by date
        seen_dates = set()
        deduped: List[Dict[str, Any]] = []
        for c in daily_candles:
            d = c["date"]
            if d in seen_dates:
                continue
            seen_dates.add(d)
            deduped.append(c)
        daily_candles = sorted(deduped, key=lambda x: x["date"])

        # 2. Get weekly backtest history for MA200w values
        weekly_history = await _load_or_build_cache()
        if not weekly_history or len(weekly_history) < WINDOW_200W:
            return {"results": [], "error": "insufficient weekly history for MA200w"}

        # Build MA200w lookup by weekly date
        weekly_prices = [safe_float(w["price"], 0.0) for w in weekly_history]
        ma200w_by_date: Dict[str, float] = {}
        for idx, item in enumerate(weekly_history):
            if idx + 1 < WINDOW_200W:
                continue
            window = weekly_prices[idx + 1 - WINDOW_200W : idx + 1]
            ma = sum(window) / len(window) if window else 0.0
            if ma > 0:
                ma200w_by_date[item["date"]] = ma

        # Build combined price history (weekly + daily) for drawdown
        all_prices_by_date: Dict[str, float] = {}
        for w in weekly_history:
            all_prices_by_date[w["date"]] = safe_float(w["price"], 0.0)
        for d in daily_candles:
            all_prices_by_date[d["date"]] = d["price"]

        # 3. Fetch FRED data (net liquidity) and Fear & Greed history
        walcl_raw, tga_raw, rrp_raw, fg_history = await asyncio.gather(
            _fetch_fred("WALCL"),
            _fetch_fred("WTREGEN"),
            _fetch_fred("RRPONTSYD"),
            _fetch_fg_history(),
        )

        # Build Net Liquidity per date
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
                    tga_val = float(tga_dict[t + delta])
                    break
            for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
                if t + delta in rrp_dict:
                    # RRP is in billions; WALCL/TGA in millions
                    rrp_val = float(rrp_dict[t + delta]) * 1000.0
                    break
            net = w - tga_val - rrp_val
            date_str = datetime.utcfromtimestamp(t // 1000).date().isoformat()
            net_liq_by_date[date_str] = net

        # Helper: last known value <= date_str (forward-fill)
        def _last_known(lookup: Dict[str, float], target_date: str, fallback: float = 50.0) -> float:
            best = None
            for d, v in sorted(lookup.items()):
                if d <= target_date:
                    best = v
                elif best is not None:
                    break
            return best if best is not None else fallback

        def _last_known_ma200w(target_date: str) -> float:
            best = None
            for d in sorted(ma200w_by_date.keys()):
                if d <= target_date:
                    best = ma200w_by_date[d]
                elif best is not None:
                    break
            return best if best is not None else 0.0

        # Build sorted all-price series for drawdown
        all_dates_sorted = sorted(all_prices_by_date.keys())
        all_prices_list = [all_prices_by_date[d] for d in all_dates_sorted]

        results: List[Dict[str, Any]] = []

        for dc in daily_candles:
            date_str = dc["date"]
            price = float(dc["price"])

            # MA200w: last known weekly MA200w value
            ma200w_val = _last_known_ma200w(date_str)
            if ma200w_val <= 0:
                continue

            ma_200w_score = ma_deviation_score(price, ma200w_val)

            # Drawdown score: based on all prices up to this date
            idx_in_all = None
            for i, d in enumerate(all_dates_sorted):
                if d == date_str:
                    idx_in_all = i
                    break
            if idx_in_all is not None and idx_in_all >= 10:
                prices_up_to = all_prices_list[: idx_in_all + 1]
                dd_score = drawdown_score(prices_up_to)
            else:
                dd_score = 50.0

            # Fear & Greed: real daily value, forward-filled
            if date_str in fg_history:
                fg_raw = fg_history[date_str]
            else:
                fg_raw = _last_known(fg_history, date_str, 50.0)
            fg_score = fg_to_score(fg_raw)

            # Net liquidity score via existing helper
            history_slice = prices_up_to if (idx_in_all is not None and idx_in_all >= 0) else []
            macro_liq = _get_net_liq_score(date_str, net_liq_by_date, history_slice)

            # ARC formula (locked weights)
            arc = (
                ma_200w_score * 0.35
                + dd_score * 0.25
                + macro_liq * 0.25
                + fg_score * 0.15
            )
            arc = max(0.0, min(100.0, arc))

            results.append(
                {
                    "date": date_str,
                    "price": round(price, 2),
                    "score": round(arc, 2),
                    "score_display": round(arc_display_score(arc), 2),
                }
            )

        # Only keep requested window
        results = sorted(results, key=lambda x: x["date"])[-days:]
        last_arc = results[-1]["score"] if results else 0.0
        logger.info("Daily backtest: %s points, last ARC=%.1f", len(results), last_arc)
        return {"results": results}

    except Exception as e:
        logger.error("Daily backtest error: %s", e, exc_info=True)
        return {"results": [], "error": str(e)}


__all__ = ["run_backtest", "run_daily_backtest"]
