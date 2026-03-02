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
    """
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(COINGECKO_URL)
        resp.raise_for_status()
        data = resp.json()

    prices = data.get("prices", []) or []
    out: List[Dict[str, Any]] = []
    for ts, price in prices:
        # ts is ms since epoch
        dt = datetime.utcfromtimestamp(ts / 1000.0).date()
        out.append(
            {
                "date": dt.isoformat(),
                "price": safe_float(price, 0.0),
            }
        )
    # Ensure sorted by date
    out.sort(key=lambda x: x["date"])
    return out


async def run_backtest() -> Dict[str, Any]:
    """
    Run historical backtest for BTC AlphaCycle score.

    For each day (after sufficient history for 200W MA approximation):
      - Compute running ATH and drawdown
      - Compute approx 200-week MA (1400-day rolling window)
      - Use placeholders:
          fear_greed = 50
          walcl_values = []
          stablecoin_supply = []
          indicators / funding / dominance left empty
      - Call existing compute_btc_score(...) on prices up to that date

    Returns dict:
      {
        "results": [
          {"date": "YYYY-MM-DD", "price": float, "score": float}
        ]
      }
    """
    history = await _fetch_btc_history()
    if not history:
        return {"results": []}

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]

    results: List[Dict[str, Any]] = []
    running_ath = 0.0
    WINDOW_200W = 1400  # ~200 weeks of daily data

    for idx, item in enumerate(history):
        price = prices[idx]
        if price <= 0:
            continue

        # Running ATH and drawdown
        running_ath = max(running_ath, price)
        if running_ath <= 0:
            drawdown = 0.0
        else:
            drawdown = (running_ath - price) / running_ath

        # Approximate 200W MA as 1400-day rolling average
        if idx + 1 < WINDOW_200W:
            # Not enough history yet — skip early period
            continue

        window_prices = prices[idx + 1 - WINDOW_200W : idx + 1]
        if not window_prices:
            continue

        ma_200w = sum(window_prices) / len(window_prices)
        if not math.isfinite(ma_200w) or ma_200w <= 0:
            continue

        # Placeholders for sentiment & liquidity
        fear_greed = 50.0
        walcl_values: List[float] = []
        stablecoin_supply: List[float] = []

        # Existing AlphaCycle BTC score function
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
                "price": price,
                "score": round(score, 2),
            }
        )

    return {"results": results}


__all__ = ["run_backtest"]

