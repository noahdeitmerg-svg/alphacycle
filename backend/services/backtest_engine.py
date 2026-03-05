"""
backtest_engine.py - Alpha Cycle Intelligence v3.0

Historical backtest: file cache /tmp/backtest_cache.json.
Once loaded, only missing days (1-2) fetched. ARC = ma_200w*0.35 + drawdown*0.35 + fg(50)*0.15 + liq(50)*0.15.
Return: [{"date": "YYYY-MM-DD", "price": float, "score": float}, ...]
"""

import asyncio
import json
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import httpx

try:
    from scoring import drawdown_score, ma_deviation_score, safe_float
except ImportError:  # pragma: no cover
    from backend.scoring import drawdown_score, ma_deviation_score, safe_float


HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
WINDOW_200W = 1400  # 200 Wochen = 1400 Tage (echter 200W MA)
CACHE_FILE = Path("/tmp/backtest_cache.json")


async def _fetch_since(since_ts: int) -> List[Dict[str, Any]]:
    """Fetch only new candles since given timestamp."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": "XBTUSD", "interval": 1440, "since": since_ts},
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
            price = float(c[4])
            if price > 0:
                dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                out.append({"date": dt, "price": price})
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
                if len(cached) < 2000:  # expect 4700+ days
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
        except Exception:
            pass

    history = await _fetch_btc_history()
    if history:
        try:
            CACHE_FILE.write_text(json.dumps(history))
        except Exception:
            pass
    return history


async def _fetch_btc_history() -> List[Dict[str, Any]]:
    """Paginated Kraken OHLC for 10 years."""
    import time as _time
    since = int(_time.time()) - (3650 * 86400)  # 10 years
    all_candles: List[list] = []

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        while True:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": "XBTUSD", "interval": 1440, "since": since},
            )
            data = resp.json()
            if data.get("error") or "result" not in data:
                break
            keys = [k for k in data["result"] if k != "last"]
            if not keys:
                break
            candles = data["result"][keys[0]]
            if not candles:
                break
            all_candles.extend(candles)
            last = data["result"].get("last", 0)
            if last <= since or len(candles) < 700:
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
            price = float(c[4])
            if price > 0:
                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                out.append({"date": dt, "price": price})
        except (IndexError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["date"])


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

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]
    results: List[Dict[str, Any]] = []
    fear_greed = 50.0
    macro_liq = 50.0

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
            ma_200w_score = ma_deviation_score(price, ma_200w)
            prices_so_far = prices[: idx + 1]
            dd_score = drawdown_score(prices_so_far)
            arc = (
                ma_200w_score * 0.35
                + dd_score * 0.35
                + fear_greed * 0.15
                + macro_liq * 0.15
            )
            arc = max(0.0, min(100.0, arc))

            results.append(
                {
                    "date": item["date"],
                    "price": round(price, 2),
                    "score": round(arc, 2),
                }
            )
    except Exception as e:
        return {"results": results, "error": f"Backtest loop: {e!s}"}

    return {"results": results}


__all__ = ["run_backtest"]
