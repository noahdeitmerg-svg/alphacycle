"""
backtest_engine.py — Alpha Cycle Intelligence v3.0

Historical backtesting engine for BTC using existing AlphaCycle score logic.

Rules:
- Uses real BTC daily prices from CoinGecko.
- Uses existing compute_btc_score from scoring.py (no rewrites).
- No database. Single-run per request.
"""

import math
from datetime import datetime
from typing import List, Dict, Any

import httpx

try:
    from scoring import compute_btc_score, safe_float
except ImportError:  # pragma: no cover
    from backend.scoring import compute_btc_score, safe_float


COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    "?vs_currency=usd&days=max"
)

HTTP_TIMEOUT = httpx.Timeout(25.0, connect=10.0)


async def _fetch_btc_history() -> List[Dict[str, Any]]:
    """Fetch BTC price history from Kraken OHLC — Railway-compatible."""
    import time as _time
    since = int(_time.time()) - (1500 * 86400)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": "XBTUSD", "interval": 1440, "since": since}
        )
        resp.raise_for_status()
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


async def run_backtest() -> Dict[str, Any]:
    """
    Run historical backtest for BTC AlphaCycle score.
    Returns {"results": [...], "error": "..."} on failure (results empty).
    """
    try:
        history = await _fetch_btc_history()
    except Exception as e:
        return {"results": [], "error": f"Fetch failed: {e!s}"}

    if not history:
        return {"results": [], "error": "No price history from API"}

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]
    results: List[Dict[str, Any]] = []
    WINDOW_200W = 1400  # ~200 weeks of daily data

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

            fear_greed = 50.0
            walcl_values: List[float] = []
            stablecoin_supply: List[float] = []

            btc_scores = compute_btc_score(
                prices_daily=prices[: idx + 1],
                fear_greed=fear_greed,
                walcl_values=walcl_values,
                stablecoin_supply=stablecoin_supply,
                indicators=None,
                funding_data=None,
                btc_dominance=None,
            )
            score = float(btc_scores.get("btc_score", 50.0))

            results.append(
                {
                    "date": item["date"],
                    "price": round(price, 2),
                    "score": round(score, 2),
                }
            )
    except Exception as e:
        return {"results": results, "error": f"Backtest loop: {e!s}"}

    return {"results": results}


__all__ = ["run_backtest"]

