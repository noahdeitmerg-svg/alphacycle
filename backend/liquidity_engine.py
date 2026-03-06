"""
liquidity_engine.py — Alpha Cycle Intelligence v3.0
Global Liquidity Regime Engine™

Detects EXPANDING / NEUTRAL / CONTRACTING liquidity regimes.
Uses WALCL, stablecoin supply, bond yields and BTC confirmation.
Zero NaN guarantee. Deterministic only.
"""

from __future__ import annotations

import math
from typing import List, Dict, Any


def _sf(v, fb: float = 0.0) -> float:
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return fb
        return f
    except Exception:
        return fb


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, _sf(v, (lo + hi) / 2.0)))


def _extract_values(series: List[Any]) -> List[float]:
    if not series:
        return []
    vals: List[float] = []
    for item in series:
        if isinstance(item, dict):
            vals.append(_sf(item.get("v", 0.0)))
        else:
            vals.append(_sf(item))
    return [v for v in vals if v > 0]


def _trend_score(values: List[float], months: int, points_per_month: int = 4) -> float:
    """
    Compute a 0-100 trend score over approx `months` months.
    Positive trend → >50, negative trend → <50.
    """
    clean = _extract_values(values)
    if len(clean) < 4:
        return 50.0

    window = max(3, min(len(clean) - 1, months * points_per_month))
    cur = clean[-1]
    prev = clean[-window - 1]
    if prev <= 0:
        return 50.0

    pct = (cur - prev) / prev * 100.0
    # Map roughly -50%..+50% to 0..100 around 50
    pct_clamped = max(-50.0, min(50.0, pct))
    return _clamp(50.0 + pct_clamped)


def _btc_confirmation_score(
    btc_prices: List[Any],
    walcl_series: List[Any],
) -> float:
    """
    Measure whether BTC is confirming liquidity direction.
    If WALCL rising and BTC rising → strong confirmation.
    If WALCL rising and BTC flat/falling → weak confirmation.
    """
    walcl_trend = _trend_score(walcl_series, months=6)
    btc_vals = _extract_values(btc_prices)
    if len(btc_vals) < 30:
        return 50.0

    # Use ~3 month window for BTC
    cur = btc_vals[-1]
    prev = btc_vals[max(0, len(btc_vals) - 90)]
    if prev <= 0:
        return 50.0

    pct = (cur - prev) / prev * 100.0
    pct_clamped = max(-80.0, min(80.0, pct))

    if walcl_trend >= 55:
        # Liquidity expanding — rising BTC = strong confirmation
        base = 60.0 + pct_clamped * 0.25
    elif walcl_trend <= 45:
        # Liquidity contracting — falling BTC = confirmation of stress
        base = 60.0 - pct_clamped * 0.20
    else:
        # Neutral liquidity — modest confirmation either way
        base = 50.0 + pct_clamped * 0.10

    return _clamp(base)


def compute_liquidity_regime(
    walcl_series: List[Any],
    stablecoin_series: List[Any],
    btc_prices: List[Any],
    eth_prices: List[Any] | None = None,
    us10y_series: List[Any] | None = None,
    dxy_series: List[Any] | None = None,
) -> Dict[str, Any]:
    """
    Core Liquidity Regime Engine.

    Inputs:
      - walcl_series: Fed balance sheet weekly series [{"t":..,"v":..}, ...]
      - stablecoin_series: total stablecoin cap series
      - btc_prices: BTC/USD daily closes
      - eth_prices: ETH/USD daily closes (optional, not yet required)
      - us10y_series: US 10Y yield series (optional)
      - dxy_series: Dollar index series (optional)

    Returns:
      {
        "liquidity_regime": "EXPANDING|NEUTRAL|CONTRACTING",
        "liquidity_score":  0-100,
        "confidence":       0-100,
        "components": {
          "walcl_trend_score":        ...,
          "stablecoin_score":         ...,
          "bond_score":               ...,
          "btc_confirmation_score":   ...,
        },
        "trend_direction": "UP|DOWN|SIDEWAYS",
        "macro_bias":      "BULLISH|NEUTRAL|BEARISH",
      }
    """
    walcl_vals = _extract_values(walcl_series)
    stable_vals = _extract_values(stablecoin_series)
    us10y_vals = _extract_values(us10y_series or [])
    dxy_vals = _extract_values(dxy_series or [])

    walcl_trend_score = _trend_score(walcl_vals, months=6)
    stable_trend_score = _trend_score(stable_vals, months=3)

    # Bond yields: rising yields = tightening → bearish liquidity
    if us10y_vals:
        current_yield = us10y_vals[-1]
        # 10Y yield: <3% = loose (low score), >5% = tight (high score)
        if current_yield < 2.0:
            bond_score = 20.0
        elif current_yield < 3.0:
            bond_score = _clamp(20.0 + (current_yield - 2.0) * 30.0)
        elif current_yield < 4.0:
            bond_score = _clamp(50.0 + (current_yield - 3.0) * 20.0)
        elif current_yield < 5.0:
            bond_score = _clamp(70.0 + (current_yield - 4.0) * 15.0)
        else:
            bond_score = _clamp(85.0 + (current_yield - 5.0) * 5.0)
    else:
        bond_score = 50.0

    btc_conf_score = _btc_confirmation_score(btc_prices, walcl_series)

    liquidity_score = (
        walcl_trend_score * 0.40 +
        stable_trend_score * 0.30 +
        bond_score * 0.15 +
        btc_conf_score * 0.15
    )
    liquidity_score = _clamp(liquidity_score)

    if liquidity_score >= 65:
        regime = "EXPANDING"
        macro_bias = "BULLISH"
    elif liquidity_score <= 40:
        regime = "CONTRACTING"
        macro_bias = "BEARISH"
    else:
        regime = "NEUTRAL"
        macro_bias = "NEUTRAL"

    # Trend direction from WALCL + stablecoins
    combined_trend = (walcl_trend_score * 0.6 + stable_trend_score * 0.4)
    if combined_trend >= 55:
        trend_direction = "UP"
    elif combined_trend <= 45:
        trend_direction = "DOWN"
    else:
        trend_direction = "SIDEWAYS"

    # Confidence: more data & stronger signal → higher confidence
    data_depth = (
        min(len(walcl_vals), 260) * 0.10 +
        min(len(stable_vals), 260) * 0.08 +
        min(len(_extract_values(btc_prices)), 365) * 0.05
    )
    data_depth = min(40.0, data_depth)

    signal_conviction = abs(liquidity_score - 50.0) * 0.8  # up to ~40
    confidence = _clamp(30.0 + data_depth + signal_conviction, 30.0, 97.0)

    return {
        "liquidity_regime": regime,
        "liquidity_score": round(liquidity_score, 1),
        "confidence": round(confidence, 1),
        "components": {
            "walcl_trend_score": round(walcl_trend_score, 1),
            "stablecoin_score": round(stable_trend_score, 1),
            "bond_score": round(bond_score, 1),
            "btc_confirmation_score": round(btc_conf_score, 1),
        },
        "trend_direction": trend_direction,
        "macro_bias": macro_bias,
    }


def compute_net_liquidity(
    walcl: float,
    tga: float = 0.0,
    rrp: float = 0.0,
    stablecoin_supply: float = 0.0,
    defi_tvl: float = 0.0,
) -> Dict[str, Any]:
    """
    Net Liquidity = WALCL - TGA - RRP.
    WALCL and TGA in millions USD; FRED RRPONTSYD in billions -> convert to millions.
    Optional: + Stablecoin Supply + DeFi TVL.
    """
    try:
        walcl = float(walcl or 0)
        tga = float(tga or 0)
        rrp_billions = float(rrp or 0)
        rrp_millions = rrp_billions * 1000
        stable = float(stablecoin_supply or 0)
        tvl = float(defi_tvl or 0)

        net_liq = walcl - tga - rrp_millions
        net_liq_extended = net_liq + stable + tvl

        return {
            "net_liquidity": round(net_liq, 2),
            "net_liquidity_extended": round(net_liq_extended, 2),
            "walcl": walcl,
            "tga": tga,
            "rrp": rrp_millions,
            "components_available": {
                "tga_available": tga > 0,
                "rrp_available": rrp > 0,
                "stable_available": stable > 0,
                "tvl_available": tvl > 0,
            },
        }
    except Exception as e:
        return {"net_liquidity": None, "error": str(e)}


__all__ = ["compute_liquidity_regime", "compute_net_liquidity"]

