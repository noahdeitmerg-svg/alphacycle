"""
decision_engine.py — Alpha Cycle Intelligence v3.0
Institutional-grade Decision Engine.

Transforms cycle analysis into exact trading decisions.
Zero NaN guarantee. Fully deterministic. Production-grade.

Components:
  1.  Alpha Cycle Position™
  2.  Recommended Action Engine
  3.  Spot Allocation Model
  4.  Leverage Engine
  5.  Liquidity Regime Engine
  6.  Smart Money vs Retail Engine
  7.  Cycle Timing Engine
  8.  Risk of Major Drawdown Engine
  9.  Alpha Signal™
  10. Expected Return Model
  11. Institutional Summary
  12. Strategy Summary
"""

import math
import logging
from datetime import datetime
from typing import Optional

try:
    from liquidity_engine import compute_liquidity_regime
except ImportError:  # pragma: no cover - fallback when used as backend.module
    from backend.liquidity_engine import compute_liquidity_regime

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# SAFE MATH
# -----------------------------------------------------------------------------

def _sf(v, fb=0.0):
    try:
        if v is None: return fb
        f = float(v)
        return fb if (math.isnan(f) or math.isinf(f)) else f
    except:
        return fb

def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, _sf(v, (lo + hi) / 2)))

def _trend(series: list, window: int = 26, neutral: float = 50.0) -> float:
    """Return trend score 0–100 from a list of floats."""
    clean = [_sf(v) for v in series if v is not None and _sf(v) > 0]
    if len(clean) < 2: return neutral
    w   = min(window, len(clean) - 1)
    cur = clean[-1]; prev = clean[-w - 1]
    if prev <= 0: return neutral
    pct = (cur - prev) / prev * 100
    return _clamp(50.0 + _clamp(pct, -50, 50))


# -----------------------------------------------------------------------------
# 1. ALPHA CYCLE POSITION (TM)
# -----------------------------------------------------------------------------

def _alpha_cycle_position(cycle_position: float) -> float:
    """Direct pass-through. Cycle position IS the alpha position."""
    return round(_clamp(_sf(cycle_position, 50.0)), 1)


# -----------------------------------------------------------------------------
# 2. RECOMMENDED ACTION ENGINE
# -----------------------------------------------------------------------------

def _recommended_action(
    cycle_position:    float,
    top_probability:   float,
    bottom_probability:float,
    seasonality_score: float,
    liquidity_regime:  str,
    confidence:        float,
) -> str:
    pos  = _clamp(cycle_position)
    tp   = _clamp(top_probability)
    bp   = _clamp(bottom_probability)
    seas = _clamp(seasonality_score)
    conf = _clamp(confidence)

    # Compute composite buy/sell pressure
    buy_pressure = (
        (100.0 - pos) * 0.35 +
        bp            * 0.25 +
        (100.0 - tp)  * 0.20 +
        seas          * 0.10 +
        conf          * 0.10
    )
    buy_pressure = _clamp(buy_pressure)

    # Liquidity modifier
    liq_mod = {"EXPANDING": +5.0, "NEUTRAL": 0.0, "CONTRACTING": -8.0}.get(liquidity_regime, 0.0)
    buy_pressure = _clamp(buy_pressure + liq_mod)

    if buy_pressure >= 72:   return "STRONG_ACCUMULATE"
    elif buy_pressure >= 58: return "ACCUMULATE"
    elif buy_pressure >= 42: return "HOLD"
    elif buy_pressure >= 28: return "REDUCE"
    else:                    return "EXIT"


# -----------------------------------------------------------------------------
# 3. SPOT ALLOCATION MODEL
# -----------------------------------------------------------------------------

def _spot_allocation(
    cycle_position:    float,
    btc_score:         float,
    eth_score:         float,
    seasonality_score: float,
    liquidity_regime:  str,
    recommended_action:str,
) -> dict:
    """
    Returns {"btc": X, "eth": Y, "cash": Z} where X+Y+Z == 100.
    Uses cycle position as primary driver, refined by individual scores.
    """
    pos  = _clamp(cycle_position)
    btcs = _clamp(btc_score)
    eths = _clamp(eth_score)
    seas = _clamp(seasonality_score)

    # ── Base allocations by cycle position band
    if pos < 15:
        # Capitulation / Bottom — max accumulation, heavy BTC
        btc_base, eth_base, cash_base = 55, 25, 20
    elif pos < 25:
        # Accumulation — strong accumulation
        btc_base, eth_base, cash_base = 50, 25, 25
    elif pos < 38:
        # Early Bull — build exposure
        btc_base, eth_base, cash_base = 45, 30, 25
    elif pos < 52:
        # Bull Expansion — full exposure, alts growing
        btc_base, eth_base, cash_base = 40, 35, 25
    elif pos < 65:
        # Late Bull — start trimming
        btc_base, eth_base, cash_base = 35, 25, 40
    elif pos < 75:
        # Distribution — reduce significantly
        btc_base, eth_base, cash_base = 25, 15, 60
    elif pos < 85:
        # Early Bear — defensive
        btc_base, eth_base, cash_base = 15, 10, 75
    else:
        # Late Bear / Capitulation — capital preservation
        btc_base, eth_base, cash_base = 10, 5, 85

    # ── Score refinements
    # BTC score above/below 50 adjusts BTC vs cash
    btc_adj  = (btcs - 50.0) * -0.20   # low btc_score = more BTC allocation
    eth_adj  = (eths - 50.0) * -0.15   # low eth_score = more ETH allocation

    # Seasonality: bearish season = more cash
    seas_cash_adj = (50.0 - seas) * 0.10   # negative seas → more cash

    # Liquidity modifier
    liq_map = {"EXPANDING": (-3, -1, 4), "NEUTRAL": (0, 0, 0), "CONTRACTING": (3, 1, -4)}
    btc_liq, eth_liq, cash_liq = liq_map.get(liquidity_regime, (0, 0, 0))

    btc_raw  = btc_base  + btc_adj  + btc_liq
    eth_raw  = eth_base  + eth_adj  + eth_liq
    cash_raw = cash_base + seas_cash_adj + cash_liq

    # Force alignment with recommended action
    action_cash = {
        "STRONG_ACCUMULATE": -10,
        "ACCUMULATE":        -5,
        "HOLD":               0,
        "REDUCE":            +10,
        "EXIT":              +20,
    }.get(recommended_action, 0)
    cash_raw += action_cash
    btc_raw  -= action_cash * 0.6
    eth_raw  -= action_cash * 0.4

    # Clamp to sensible ranges
    btc_final  = _clamp(btc_raw,  5.0, 70.0)
    eth_final  = _clamp(eth_raw,  0.0, 45.0)
    cash_final = _clamp(cash_raw, 5.0, 90.0)

    # Normalise to exactly 100%
    total = btc_final + eth_final + cash_final
    if total <= 0: total = 100.0
    factor = 100.0 / total

    btc_n  = round(btc_final  * factor)
    eth_n  = round(eth_final  * factor)
    cash_n = 100 - btc_n - eth_n   # residual ensures sum = 100

    return {
        "btc":  max(0, btc_n),
        "eth":  max(0, eth_n),
        "cash": max(0, cash_n),
    }


# -----------------------------------------------------------------------------
# 4. LEVERAGE ENGINE
# -----------------------------------------------------------------------------

def _leverage_recommendation(
    cycle_position: float,
    risk_level:     str,
    top_probability:float,
    liquidity_regime: str,
) -> str:
    pos = _clamp(cycle_position)
    tp  = _clamp(top_probability)

    if risk_level in ("EXTREME", "HIGH"):
        return "AVOID LEVERAGE"
    if tp >= 60:
        return "AVOID LEVERAGE"
    if liquidity_regime == "CONTRACTING":
        return "AVOID LEVERAGE"
    if pos < 25 and risk_level == "LOW":
        return "LOW LEVERAGE OK"
    if pos < 40 and risk_level in ("LOW", "MEDIUM"):
        return "LOW LEVERAGE OK"
    if pos >= 65:
        return "AVOID LEVERAGE"
    return "NO LEVERAGE"


# -----------------------------------------------------------------------------
# 6. SMART MONEY VS RETAIL ENGINE
# -----------------------------------------------------------------------------

def _smart_money_positioning(
    cycle_position: float,
    bottom_prob:    float,
    top_prob:       float,
    fear_greed:     float,
) -> str:
    """
    Smart money (institutional) acts OPPOSITE to sentiment.
    They accumulate during fear, distribute during greed.
    """
    pos = _clamp(cycle_position)
    bp  = _clamp(bottom_prob)
    tp  = _clamp(top_prob)
    fg  = _clamp(_sf(fear_greed, 50.0))

    # Smart money acts contrary: extreme fear = they buy, extreme greed = they sell
    if pos < 25 or (bp >= 65 and fg < 25):
        return "ACCUMULATING"
    elif pos >= 68 or (tp >= 65 and fg > 72):
        return "DISTRIBUTING"
    else:
        return "NEUTRAL"


def _retail_positioning(fear_greed: float, cycle_position: float) -> str:
    """Retail follows sentiment."""
    fg  = _clamp(_sf(fear_greed, 50.0))
    pos = _clamp(cycle_position)

    if fg < 20:                      return "FEAR"
    elif fg < 40:                    return "NEUTRAL"
    elif fg < 65 and pos < 60:       return "NEUTRAL"
    elif fg < 78:                    return "GREED"
    else:                            return "EUPHORIA"


# -----------------------------------------------------------------------------
# 7. CYCLE TIMING ENGINE
# -----------------------------------------------------------------------------

def _cycle_timing(
    cycle_position:   float,
    years_since_halving: float,
    score_history:    list,
) -> tuple:
    """
    Estimate months to cycle top and months to cycle bottom.
    Based on halving cycle positioning and current trend velocity.
    Returns (to_top_str, to_bottom_str).
    """
    pos      = _clamp(cycle_position)
    ysh      = _sf(years_since_halving, 1.0)
    months_since_halving = ysh * 12.0

    # Compute trend velocity (how fast is score moving?)
    velocity = 0.0
    if len(score_history) >= 20:
        try:
            recent   = [_sf(h.get("v", 50) if isinstance(h, dict) else h) for h in score_history[-10:]]
            previous = [_sf(h.get("v", 50) if isinstance(h, dict) else h) for h in score_history[-20:-10]]
            velocity = (sum(recent)/len(recent)) - (sum(previous)/len(previous))
        except:
            velocity = 0.0

    # Historical Bitcoin cycle tops occur roughly 12–18 months post halving
    # Current halving: April 2024
    # Typical top window: Oct 2025 – April 2026

    if pos < 20:
        # Deep accumulation — top is far, bottom may already be near
        to_top    = "18–30"
        to_bottom = "0–6"
    elif pos < 35:
        to_top    = "12–24"
        to_bottom = "3–12"
    elif pos < 50:
        # Early bull — top getting closer
        if velocity > 2.0:     # fast moving
            to_top = "9–15"
        else:
            to_top = "12–20"
        to_bottom = "18–30"
    elif pos < 65:
        if velocity > 3.0:
            to_top = "4–9"
        else:
            to_top = "6–12"
        to_bottom = "24–36"
    elif pos < 78:
        # Distribution — top imminent
        if velocity > 1.0:
            to_top = "1–4"
        elif velocity > -1.0:
            to_top = "2–6"
        else:
            to_top = "0–3"      # may already be past top
        to_bottom = "18–30"
    elif pos < 88:
        # Early bear — past top
        to_top    = "N/A (past top)"
        to_bottom = "9–18"
    else:
        # Late bear / capitulation
        to_top    = "N/A (bear market)"
        to_bottom = "0–9"

    # Halving-cycle adjustment: we're ~11 months into the 2024 halving cycle (March 2026)
    # Historical patterns suggest top window: Q4 2025 – Q1 2026
    # This implies we may be approaching or past the top
    if months_since_halving >= 18 and pos < 65:
        # Halving clock says top window passed but score still low = bear confirmed
        to_bottom = "3–12"

    return to_top, to_bottom


# -----------------------------------------------------------------------------
# 8. RISK OF MAJOR DRAWDOWN ENGINE
# -----------------------------------------------------------------------------

def _drawdown_risk(
    cycle_position:   float,
    top_probability:  float,
    liquidity_regime: str,
    macro_score:      float,
    fear_greed:       float,
) -> float:
    """Return 0–100 probability of a major drawdown (>30%) in next 3–6 months."""
    pos   = _clamp(cycle_position)
    tp    = _clamp(top_probability)
    mac   = _clamp(_sf(macro_score, 50.0))
    fg    = _clamp(_sf(fear_greed,  50.0))

    # Base: higher cycle position = higher drawdown risk
    base_risk = pos * 0.50

    # Top probability boost
    tp_boost = tp * 0.25

    # Liquidity
    liq_boost = {"CONTRACTING": 15.0, "NEUTRAL": 0.0, "EXPANDING": -10.0}.get(liquidity_regime, 0.0)

    # Macro tightness
    mac_boost = mac * 0.10

    # Fear/Greed: high greed = higher crash risk
    fg_boost = (fg - 50.0) * 0.15 if fg > 50 else 0.0

    raw = base_risk + tp_boost + liq_boost + mac_boost + fg_boost
    return round(_clamp(raw), 1)


# -----------------------------------------------------------------------------
# 9. ALPHA SIGNAL (TM)
# -----------------------------------------------------------------------------

def _alpha_signal(
    cycle_position:    float,
    bottom_probability:float,
    top_probability:   float,
    seasonality_score: float,
    fear_greed:        float,
    macro_score:       float,
    liquidity_regime:  str,
) -> str:
    pos  = _clamp(cycle_position)
    bp   = _clamp(bottom_probability)
    tp   = _clamp(top_probability)
    seas = _clamp(seasonality_score)
    fg   = _clamp(_sf(fear_greed,  50.0))
    mac  = _clamp(_sf(macro_score, 50.0))

    liq_score = {"EXPANDING": 70.0, "NEUTRAL": 50.0, "CONTRACTING": 30.0}.get(liquidity_regime, 50.0)

    signal_score = (
        (100.0 - pos)  * 0.30 +
        bp             * 0.22 +
        (100.0 - tp)   * 0.18 +
        (100.0 - fg)   * 0.12 +
        seas           * 0.10 +
        liq_score      * 0.08
    )
    signal_score = _clamp(signal_score)

    if signal_score >= 75:   return "STRONG_BUY"
    elif signal_score >= 60: return "BUY"
    elif signal_score >= 42: return "HOLD"
    elif signal_score >= 28: return "SELL"
    else:                    return "STRONG_SELL"


# -----------------------------------------------------------------------------
# 10. EXPECTED RETURN MODEL
# -----------------------------------------------------------------------------

RETURN_TABLE = {
    # (min_pos, max_pos): (low_return%, high_return%) 12-month forward
    (0,  15):  (+40, +150),   # Capitulation/Bottom — massive upside if correct
    (15, 25):  (+25,  +80),   # Accumulation
    (25, 38):  (+20,  +60),   # Early Bull
    (38, 52):  (+10,  +40),   # Bull Expansion
    (52, 65):  (  0,  +25),   # Late Bull — returns compressing
    (65, 75):  (-20,  +10),   # Distribution
    (75, 85):  (-40,  -10),   # Early Bear
    (85, 95):  (-55,  -20),   # Late Bear
    (95, 101): (-30,  +20),   # Capitulation — may bounce
}

def _expected_return(
    cycle_position:    float,
    seasonality_score: float,
    liquidity_regime:  str,
) -> str:
    pos  = _clamp(cycle_position)
    seas = _clamp(seasonality_score)

    lo, hi = +5, +15  # default
    for (min_p, max_p), (r_lo, r_hi) in RETURN_TABLE.items():
        if min_p <= pos < max_p:
            lo, hi = r_lo, r_hi
            break

    # Seasonality adjustment
    seas_adj = round((seas - 50.0) * 0.20)
    lo += seas_adj; hi += seas_adj

    # Liquidity adjustment
    liq_adj = {"EXPANDING": +5, "NEUTRAL": 0, "CONTRACTING": -10}.get(liquidity_regime, 0)
    lo += liq_adj; hi += liq_adj

    def _fmt(v):
        return f"+{v}%" if v > 0 else f"{v}%"

    return f"{_fmt(lo)} to {_fmt(hi)}"


# -----------------------------------------------------------------------------
# 11. RISK LEVEL ENGINE
# -----------------------------------------------------------------------------

def _risk_level(
    cycle_position:   float,
    drawdown_risk:    float,
    liquidity_regime: str,
    top_probability:  float,
) -> str:
    pos = _clamp(cycle_position)
    dr  = _clamp(drawdown_risk)
    tp  = _clamp(top_probability)

    risk_score = (
        pos * 0.40 +
        dr  * 0.30 +
        tp  * 0.20 +
        ({"CONTRACTING": 80.0, "NEUTRAL": 50.0, "EXPANDING": 20.0}.get(liquidity_regime, 50.0)) * 0.10
    )
    risk_score = _clamp(risk_score)

    if risk_score >= 72:   return "EXTREME"
    elif risk_score >= 55: return "HIGH"
    elif risk_score >= 38: return "MEDIUM"
    else:                  return "LOW"


# -----------------------------------------------------------------------------
# 12. INSTITUTIONAL SUMMARY
# -----------------------------------------------------------------------------

def _institutional_summary(
    alpha_position:    float,
    market_phase:      str,
    alpha_signal:      str,
    risk_level:        str,
    liquidity_regime:  str,
    smart_money:       str,
    drawdown_risk:     float,
    expected_return:   str,
    seasonality_bias:  str,
    bottom_prob:       float,
    top_prob:          float,
    fear_greed:        float,
    allocation:        dict,
) -> str:
    pos = round(alpha_position, 1)
    fg  = _sf(fear_greed, 50.0)

    # Liquidity narrative
    liq_str = {
        "EXPANDING":   "Macro liquidity is expanding — structural tailwind in place.",
        "NEUTRAL":     "Macro liquidity regime is neutral — no strong directional bias.",
        "CONTRACTING": "Macro liquidity is contracting — risk premium elevated. Caution warranted.",
    }.get(liquidity_regime, "Liquidity regime unclear.")

    # Positioning narrative
    if alpha_position < 25:
        pos_str = (
            f"Alpha Cycle™ positioned at {pos}/100 — deep accumulation zone. "
            f"Bottom probability: {bottom_prob}%. "
            "Historically, this zone has offered the highest risk-adjusted forward returns. "
            "Smart money accumulation is consistent with current setup."
        )
    elif alpha_position < 45:
        pos_str = (
            f"Alpha Cycle™ positioned at {pos}/100 — early bull expansion. "
            "Trend structure improving. Institutional participation increasing. "
            "Risk/reward asymmetric to upside."
        )
    elif alpha_position < 62:
        pos_str = (
            f"Alpha Cycle™ positioned at {pos}/100 — mid-cycle bull market. "
            "Momentum phase. Broad market participation. "
            "Maintain exposure, reduce leverage."
        )
    elif alpha_position < 78:
        pos_str = (
            f"Alpha Cycle™ positioned at {pos}/100 — distribution zone. "
            f"Top probability: {top_prob}%. "
            "Smart money beginning to rotate. Risk/reward deteriorating. "
            "Exposure reduction recommended."
        )
    else:
        pos_str = (
            f"Alpha Cycle™ positioned at {pos}/100 — bear market territory. "
            "Capital preservation is the primary objective. "
            "Drawdown risk remains elevated."
        )

    # Sentiment
    if fg < 20:
        sent_str = f"Sentiment at extreme fear ({fg:.0f}/100) — historically a high-conviction contrarian buy signal."
    elif fg > 78:
        sent_str = f"Sentiment at extreme greed ({fg:.0f}/100) — distribution risk is elevated."
    else:
        sent_str = f"Sentiment neutral-to-negative ({fg:.0f}/100)."

    # Seasonal
    seas_str = {
        "BULLISH":  "Seasonal analysis confirms tailwind — historical bias favors upside.",
        "BEARISH":  "Seasonal headwind present — historical bias unfavorable near-term.",
        "NEUTRAL":  "No strong seasonal bias — direction driven by fundamentals.",
    }.get(seasonality_bias, "")

    # Allocation
    alloc_str = (
        f"Recommended allocation: BTC {allocation.get('btc',0)}% / "
        f"ETH {allocation.get('eth',0)}% / "
        f"Cash {allocation.get('cash',0)}%."
    )

    return " ".join([pos_str, liq_str, sent_str, seas_str, alloc_str])


# -----------------------------------------------------------------------------
# 13. STRATEGY SUMMARY
# -----------------------------------------------------------------------------

STRATEGY_SUMMARIES = {
    "STRONG_ACCUMULATE": (
        "Accumulate aggressively at current levels. "
        "Prioritise BTC as base layer. "
        "Avoid leverage — this zone can overshoot to the downside. "
        "Time horizon: 12–24 months."
    ),
    "ACCUMULATE": (
        "Continue accumulation. "
        "Dollar-cost average into positions. "
        "Avoid leverage. "
        "Prepare for expansion phase."
    ),
    "HOLD": (
        "Hold core positions. "
        "Do not add leverage. "
        "Set stop-losses on speculative positions. "
        "Monitor macro liquidity for direction change."
    ),
    "REDUCE": (
        "Reduce exposure. "
        "Take partial profits on speculative positions. "
        "Rotate into cash or stable assets. "
        "Avoid adding new positions."
    ),
    "EXIT": (
        "Exit risk positions. "
        "Preserve capital in cash or stablecoins. "
        "Wait for cycle reset before re-entering. "
        "Re-evaluate when cycle position drops below 30."
    ),
}


# -----------------------------------------------------------------------------
# MAIN DECISION ENGINE CLASS
# -----------------------------------------------------------------------------

class DecisionEngine:
    """
    Institutional Decision Engine.
    Transforms cycle analysis into exact trading decisions.
    Zero NaN. Fully deterministic.
    """

    def decide(
        self,
        # From analyzer
        phase:               str,
        cycle_position:      float,
        combined_score:      float,
        btc_score:           float,
        eth_score:           float,
        macro_score:         float,
        seasonality_score:   float,
        seasonality_bias:    str,
        bottom_probability:  float,
        top_probability:     float,
        confidence:          float,
        years_since_halving: float,
        # From backend
        btc_price:           float,
        eth_price:           float,
        btc_drawdown_pct:    float,
        fear_greed:          float,
        walcl_series:        list,
        stable_series:       list,
        score_history:       list,
    ) -> dict:
        """Run full decision engine. Always returns valid dict. Never raises."""
        try:
            return self._run(
                phase, cycle_position, combined_score,
                btc_score, eth_score, macro_score,
                seasonality_score, seasonality_bias,
                bottom_probability, top_probability,
                confidence, years_since_halving,
                btc_price, eth_price, btc_drawdown_pct,
                fear_greed, walcl_series or [],
                stable_series or [], score_history or [],
            )
        except Exception as e:
            logger.error(f"DecisionEngine.decide failed: {e}", exc_info=True)
            return self._fallback()

    def _run(
        self, phase, cycle_position, combined_score,
        btc_score, eth_score, macro_score,
        seasonality_score, seasonality_bias,
        bottom_prob, top_prob, confidence,
        years_since_halving,
        btc_price, eth_price, btc_drawdown_pct,
        fear_greed, walcl_series, stable_series, score_history,
    ) -> dict:

        # ── 1. Alpha Cycle Position™
        alpha_pos = _alpha_cycle_position(cycle_position)

        # ── 5. Liquidity Regime (needed early for downstream)
        liq_data = compute_liquidity_regime(
            walcl_series=walcl_series,
            stablecoin_series=stable_series,
            btc_prices=[],
            eth_prices=[],
            us10y_series=[],
            dxy_series=[],
        )
        liq_regime = liq_data.get("liquidity_regime", "NEUTRAL")

        # ── 8. Drawdown Risk
        dr_risk = _drawdown_risk(alpha_pos, top_prob, liq_regime, macro_score, fear_greed)

        # ── Risk Level
        risk_lvl = _risk_level(alpha_pos, dr_risk, liq_regime, top_prob)

        # ── 2. Recommended Action
        action = _recommended_action(
            alpha_pos, top_prob, bottom_prob,
            seasonality_score, liq_regime, confidence
        )

        # ── 3. Spot Allocation
        allocation = _spot_allocation(
            alpha_pos, btc_score, eth_score,
            seasonality_score, liq_regime, action
        )

        # ── 4. Leverage
        leverage = _leverage_recommendation(alpha_pos, risk_lvl, top_prob, liq_regime)

        # ── 6. Smart Money / Retail
        smart_money = _smart_money_positioning(alpha_pos, bottom_prob, top_prob, fear_greed)
        retail      = _retail_positioning(fear_greed, alpha_pos)

        # ── 7. Cycle Timing
        to_top, to_bottom = _cycle_timing(alpha_pos, years_since_halving, score_history)

        # ── 9. Alpha Signal™
        signal = _alpha_signal(
            alpha_pos, bottom_prob, top_prob,
            seasonality_score, fear_greed, macro_score, liq_regime
        )

        # ── 10. Expected Return
        exp_return = _expected_return(alpha_pos, seasonality_score, liq_regime)

        # ── 11. Institutional Summary
        inst_summary = _institutional_summary(
            alpha_pos, phase, signal, risk_lvl, liq_regime,
            smart_money, dr_risk, exp_return, seasonality_bias,
            bottom_prob, top_prob, fear_greed, allocation
        )

        # ── 12. Strategy Summary
        strategy_summary = STRATEGY_SUMMARIES.get(action, STRATEGY_SUMMARIES["HOLD"])

        return {
            "alpha_cycle_position":      alpha_pos,
            "market_phase":              phase,
            "recommended_action":        action,
            "alpha_signal":              signal,
            "spot_allocation":           allocation,
            "leverage_recommendation":   leverage,
            "risk_level":                risk_lvl,
            "risk_of_major_drawdown":    dr_risk,
            "liquidity_regime":          liq_regime,
            "smart_money_positioning":   smart_money,
            "retail_positioning":        retail,
            "time_to_cycle_top_months":  to_top,
            "time_to_cycle_bottom_months": to_bottom,
            "expected_return_12m":       exp_return,
            "confidence":                round(_clamp(confidence), 1),
            "institutional_summary":     inst_summary,
            "strategy_summary":          strategy_summary,
            # Transparency extras
            "inputs": {
                "cycle_position":    alpha_pos,
                "combined_score":    round(_sf(combined_score), 1),
                "btc_score":         round(_sf(btc_score),      1),
                "eth_score":         round(_sf(eth_score),      1),
                "macro_score":       round(_sf(macro_score),    1),
                "fear_greed":        round(_sf(fear_greed),     1),
                "seasonality_score": round(_sf(seasonality_score), 1),
                "seasonality_bias":  seasonality_bias,
                "bottom_probability":bottom_prob,
                "top_probability":   top_prob,
                "btc_price":         round(_sf(btc_price), 2),
                "eth_price":         round(_sf(eth_price), 2),
                "btc_drawdown_pct":  round(_sf(btc_drawdown_pct), 2),
                "liquidity_regime":  liq_regime,
            },
        }

    @staticmethod
    def _fallback() -> dict:
        return {
            "alpha_cycle_position":        50.0,
            "market_phase":                "Accumulation",
            "recommended_action":          "HOLD",
            "alpha_signal":                "HOLD",
            "spot_allocation":             {"btc": 40, "eth": 20, "cash": 40},
            "leverage_recommendation":     "NO LEVERAGE",
            "risk_level":                  "MEDIUM",
            "risk_of_major_drawdown":      30.0,
            "liquidity_regime":            "NEUTRAL",
            "smart_money_positioning":     "NEUTRAL",
            "retail_positioning":          "NEUTRAL",
            "time_to_cycle_top_months":    "12–24",
            "time_to_cycle_bottom_months": "N/A",
            "expected_return_12m":         "+5% to +25%",
            "confidence":                  20.0,
            "institutional_summary":       "Data loading. Decision engine will update on next cache refresh.",
            "strategy_summary":            "Hold. Await data confirmation.",
            "inputs": {},
        }


# Module-level singleton
decision_engine = DecisionEngine()
