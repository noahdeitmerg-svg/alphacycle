"""
backtest_engine.py - Alpha Cycle Intelligence v3.0

Historical backtest: paginated Kraken OHLC (max 720/request).
ARC = ma_200w*0.35 + drawdown*0.35 + fear_greed(50)*0.15 + macro_liq(50)*0.15.
Return: [{"date": "YYYY-MM-DD", "price": float, "score": float}, ...]
"""

import asyncio
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any

import httpx

try:
    from scoring import drawdown_score, ma_deviation_score, safe_float
except ImportError:  # pragma: no cover
    from backend.scoring import drawdown_score, ma_deviation_score, safe_float


HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
WINDOW_200W = 1400  # ~200 weeks daily


async def fetch_kraken_ohlc_full(pair: str = "XBTUSD", years: int = 10) -> List[list]:
    """Paginated Kraken OHLC for up to 10 years (max 720 candles per request)."""
    since = int((datetime.utcnow() - timedelta(days=365 * years)).timestamp())
    all_candles: List[list] = []

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        while True:
            r = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": pair, "interval": 1440, "since": since},
            )
            data = r.json()
            if data.get("error") or "result" not in data:
                break
            result = data["result"]
            keys = [k for k in result if k != "last"]
            if not keys:
                break
            key = keys[0]
            candles = result[key]
            if not candles:
                break
            all_candles.extend(candles)
            last = result.get("last", 0)
            if last <= since or len(candles) < 700:
                break
            since = last
            await asyncio.sleep(1)

    return all_candles


def _candles_to_history(candles: List[list]) -> List[Dict[str, Any]]:
    """Convert raw Kraken candles to list of {date, price} sorted by date."""
    seen = set()
    out = []
    for c in candles:
        try:
            ts = int(c[0])
            if ts in seen:
                continue
            seen.add(ts)
            price = float(c[4])
            if price <= 0:
                continue
            dt = datetime.utcfromtimestamp(ts).date().isoformat()
            out.append({"date": dt, "price": price})
        except (IndexError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["date"])
    return out


async def run_backtest() -> Dict[str, Any]:
    """
    Run historical backtest. Returns {"results": [{"date", "price", "score"}, ...], "error": "..."} on failure.
    """
    try:
        candles = await fetch_kraken_ohlc_full("XBTUSD", years=10)
    except Exception as e:
        return {"results": [], "error": f"Fetch failed: {e!s}"}

    history = _candles_to_history(candles)
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
