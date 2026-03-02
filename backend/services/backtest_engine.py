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
    """
    Fetch full BTC price history from CoinGecko.
    Returns list of {"date": "YYYY-MM-DD", "price": float} sorted by date.
    Deduplicates by date (last price of day).
    """
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(COINGECKO_URL)
        resp.raise_for_status()
        data = resp.json()

    prices_raw = data.get("prices", []) or []
    by_date: Dict[str, float] = {}
    for item in prices_raw:
        try:
            ts = item[0] if isinstance(item, (list, tuple)) else item.get("timestamp", 0)
            price = item[1] if isinstance(item, (list, tuple)) else item.get("value", 0)
            dt = datetime.utcfromtimestamp(float(ts) / 1000.0).date()
            key = dt.isoformat()
            by_date[key] = safe_float(price, 0.0)
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    out = [{"date": k, "price": v} for k, v in sorted(by_date.items())]
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

