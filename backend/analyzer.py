"""
analyzer.py — Alpha Cycle Intelligence v3.0
Institutional-grade Cycle Analyzer Engine.

Components:
  1. Cycle Phase Model       (10 phases, 0-100 positioning)
  2. Wall Street Psychology  (13 emotional phases)
  3. Seasonality Engine      (Seasonax-style: month/quarter/halving cycle)
  4. Probability Engine      (bottom/top probability)
  5. Forecast Engine         (next phase, next major event)
  6. Signal Engine           (STRONG_BUY → STRONG_SELL)
  7. Risk Engine             (LOW → EXTREME)
  8. Institutional Summary
  9. Retail Summary
  10. Strategy Output

Zero NaN guarantee. All fields always populated.
"""

import math
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

# Known cycle top for post-top phase detection (Oct 2025)
CYCLE_TOP_DATE = datetime(2025, 10, 6, tzinfo=timezone.utc)


def compute_days_since_top() -> int:
    now = datetime.now(timezone.utc)
    delta = now - CYCLE_TOP_DATE
    return max(0, delta.days)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# ARC MOMENTUM + PERCENTILE
# -----------------------------------------------------------------------------

def compute_arc_momentum(arc_history: list, current_arc: float) -> dict:
    """
    arc_history: list of dicts with date + arc_score (or score), sorted by date.
    Computes 30d momentum and percentile rank.
    """
    try:
        if not arc_history or len(arc_history) < 5:
            return {
                "arc_momentum_30d": None,
                "arc_momentum_label": "Insufficient data",
                "arc_percentile": None,
                "arc_percentile_label": None,
            }
        hist = sorted(arc_history, key=lambda x: x.get("date", ""))
        WEEKS_30D = 4
        arc_30d_ago = float(
            hist[-(WEEKS_30D + 1)].get("arc_score", hist[-(WEEKS_30D + 1)].get("score", current_arc))
        ) if len(hist) >= WEEKS_30D + 1 else float(hist[0].get("arc_score", hist[0].get("score", current_arc)))
        momentum = round(current_arc - arc_30d_ago, 1)
        if momentum < -10:
            m_label = "Risk decreasing"
        elif momentum > 10:
            m_label = "Risk increasing"
        elif momentum < -3:
            m_label = "Risk slightly decreasing"
        elif momentum > 3:
            m_label = "Risk slightly increasing"
        else:
            m_label = "Risk stable"
        all_scores = [
            float(h.get("arc_score", h.get("score", 50)))
            for h in hist
            if h.get("arc_score") is not None or h.get("score") is not None
        ]
        if all_scores:
            below = sum(1 for s in all_scores if s <= current_arc)
            percentile = round(below / len(all_scores) * 100)
        else:
            percentile = 50
        if percentile < 20:
            p_label = "Historically favorable"
        elif percentile < 40:
            p_label = "Below average risk"
        elif percentile < 60:
            p_label = "Average risk"
        elif percentile < 80:
            p_label = "Above average risk"
        else:
            p_label = "Historically elevated"
        return {
            "arc_momentum_30d": momentum,
            "arc_momentum_label": m_label,
            "arc_percentile": percentile,
            "arc_percentile_label": p_label,
        }
    except Exception as e:
        logger.warning("compute_arc_momentum error: %s", e)
        return {
            "arc_momentum_30d": None,
            "arc_momentum_label": "Error",
            "arc_percentile": None,
            "arc_percentile_label": None,
            "error": str(e),
        }


def compute_confidence_calibrated(
    arc: float,
    fear_greed: float,
    momentum: float,
    percentile: int,
    win_rate: Optional[float] = None,
) -> Tuple[float, str]:
    """
    Returns (confidence_pct, label). Factors: ARC extremeness, momentum confirmation,
    historical win rate, percentile extremes.
    """
    score = 0.0
    a = max(0.0, min(100.0, float(arc or 50)))
    m = float(momentum) if momentum is not None else 0.0
    pct = int(percentile) if percentile is not None else 50

    arc_dist = abs(a - 50)
    score += arc_dist * 0.8

    if a < 50 and m < 0:
        score += 15
    elif a > 50 and m > 0:
        score += 15
    else:
        score += 5

    if win_rate is not None:
        score += (win_rate - 50) * 0.3

    if pct < 15 or pct > 85:
        score += 10
    elif pct < 25 or pct > 75:
        score += 5

    confidence = min(95.0, max(20.0, score))

    if confidence >= 80:
        label = "High"
    elif confidence >= 60:
        label = "Moderate-High"
    elif confidence >= 40:
        label = "Moderate"
    else:
        label = "Low"

    return round(confidence, 1), label


# -----------------------------------------------------------------------------
# CYCLE SIGNAL DETECTION (Top/Bottom)
# -----------------------------------------------------------------------------

def detect_cycle_signal(
    arc_score: float,
    drawdown_pct: float,
    fear_greed: float,
    rsi_weekly: float,
    liquidity_score: float,
    funding_score: float,
    price: float,
    ma_200w: float,
) -> dict:
    """
    Erkennt Cycle Top/Bottom Signale basierend auf
    multiplen Indikatoren. Gibt ein strukturiertes
    Signal-Objekt zurueck.

    Rueckgabe:
    signal_type: NONE|BOTTOM_WATCH|BOTTOM_WARNING|BOTTOM_CONFIRMED|
                 TOP_WATCH|TOP_WARNING|TOP_CONFIRMED
    signal_strength: 0-100
    bottom_conditions_met / top_conditions_met: 0-5
    description, decision_override (optional)
    """
    arc = max(0.0, min(100.0, float(arc_score or 50)))
    dd = max(0.0, min(1.0, float(drawdown_pct or 0)))
    fg = max(0.0, min(100.0, float(fear_greed or 50)))
    rsi = max(0.0, min(100.0, float(rsi_weekly or 50)))
    liq = max(0.0, min(100.0, float(liquidity_score or 50)))
    funding = max(0.0, min(100.0, float(funding_score or 50)))
    ma200w = float(ma_200w or 0)
    btc_price = float(price or 0)

    bottom_conditions = [
        arc < 30,
        dd > 0.55,
        fg < 30,
        rsi < 35,
        liq > 30,
    ]
    bottom_count = sum(bottom_conditions)

    price_extended = (btc_price > ma200w * 2.5) if ma200w > 0 else False
    top_conditions = [
        arc > 75,
        funding > 65,
        fg > 75,
        liq < 40,
        price_extended,
    ]
    top_count = sum(top_conditions)

    if arc < 45:
        if arc < 30 and bottom_count >= 4:
            signal_type = "BOTTOM_CONFIRMED"
            strength = min(100, int(60 + (30 - arc) * 2))
            desc = "Bestaetigtes Cycle Bottom - strukturelle Kaufzone"
            override = "BUY"
        elif arc < 35 and bottom_count >= 3:
            signal_type = "BOTTOM_WARNING"
            strength = min(100, int(40 + bottom_count * 8))
            desc = "Bottom Warning - moegliche Akkumulationszone"
            try:
                from decision_engine import get_position
                override = get_position(arc, 0, 50)
            except Exception:
                override = "BUY"
        elif arc < 40 and bottom_count >= 2:
            signal_type = "BOTTOM_WATCH"
            strength = min(100, int(20 + bottom_count * 8))
            desc = "Bottom Watch - ARC in niedrigem Bereich"
            override = None
        else:
            signal_type = "NONE"
            strength = 0
            desc = "Kein aktives Signal"
            override = None
    elif arc > 60:
        if arc > 78 and top_count >= 4:
            signal_type = "TOP_CONFIRMED"
            strength = min(100, int(60 + (arc - 78) * 2))
            desc = "Bestaetigtes Cycle Top - Distributionszone"
            override = "RISK OFF"
        elif arc > 72 and top_count >= 3:
            signal_type = "TOP_WARNING"
            strength = min(100, int(40 + top_count * 8))
            desc = "Top Warning - Risikoreduktion empfohlen"
            override = "REDUCE"
        elif arc > 65 and top_count >= 2:
            signal_type = "TOP_WATCH"
            strength = min(100, int(20 + top_count * 8))
            desc = "Top Watch - erhoehte Vorsicht"
            override = None
        else:
            signal_type = "NONE"
            strength = 0
            desc = "Kein aktives Signal"
            override = None
    else:
        signal_type = "NONE"
        strength = 0
        desc = "Neutraler Bereich - kein Extremsignal"
        override = None

    return {
        "signal_type": signal_type,
        "signal_strength": strength,
        "bottom_conditions_met": bottom_count,
        "top_conditions_met": top_count,
        "description": desc,
        "decision_override": override,
        "arc_at_signal": round(arc, 1),
        "conditions_detail": {
            "arc_low": arc < 30,
            "drawdown_deep": dd > 0.55,
            "fear_extreme": fg < 30,
            "rsi_oversold": rsi < 35,
            "liq_stable": liq > 30,
            "arc_high": arc > 75,
            "funding_hot": funding > 65,
            "greed_extreme": fg > 75,
            "liq_contracting": liq < 40,
            "price_extended": price_extended,
        },
    }


# -----------------------------------------------------------------------------
# SHORT TERM CONTEXT (30-90d tactical)
# -----------------------------------------------------------------------------

def get_short_term_context(
    arc_score: float,
    days_since_bottom: int,
    rsi_score: float,
    funding_score: float,
    power_law_score: float,
    mvrv_score: float,
    btc_price: float,
    ath_price: float,
    ma_200w: float,
    drawdown_pct: float = 0.0,
) -> dict:
    """
    Berechnet taktischen Kontext fuer 30-90 Tage.
    Gibt Cycle Phase Label, Upside/Downside Szenario
    und aggregierten Short Term Score zurueck.
    Post-Top-Erkennung hat Prioritaet (Late Bull -> Early Bear).
    """
    arc = max(0.0, min(100.0, float(arc_score or 50)))
    days = max(0, int(days_since_bottom or 0))
    days_since_top = compute_days_since_top()
    rsi = max(0.0, min(100.0, float(rsi_score or 50)))
    funding = max(0.0, min(100.0, float(funding_score or 50)))
    pl = max(0.0, min(100.0, float(power_law_score or 50)))
    mvrv = max(0.0, min(100.0, float(mvrv_score or 50)))
    price = max(0.0, float(btc_price or 0))
    ath = max(0.0, float(ath_price or price or 1))
    ma200w = max(0.0, float(ma_200w or 0))

    st_score = round((rsi + funding + pl + mvrv) / 4)
    st_score = max(0, min(100, st_score))

    # Post-Top Detection has priority
    if days_since_top > 0 and days_since_top < 180:
        if arc >= 60:
            phase_label = "Bear / Risk Off"
            phase_desc = "Post-Top Abschwung. Kapitalerhalt Prioritaet."
        elif arc >= 40:
            phase_label = "Early Bear"
            phase_desc = "Korrekturphase nach Cycle Top. Strukturelles Risiko faellt."
        else:
            phase_label = "Early Bear"
            phase_desc = "Tief-Korrektur. ARC naehert sich Akkumulationszone."
    elif days_since_top >= 180 and days_since_top < 540:
        if arc < 35:
            phase_label = "Late Bear / Accumulation"
            phase_desc = "Spaeter Abschwung. Historische Kaufzone naehert sich."
        elif arc < 55:
            phase_label = "Late Bear"
            phase_desc = "Uebergangsphase. Cycle Reset laeuft."
        else:
            phase_label = "Distribution"
            phase_desc = "Erholung mit erhoehtem Risiko."
    else:
        # New cycle or no top known
        if arc < 30:
            phase_label = "Early Bull"
            phase_desc = "Fruehe Aufwaertsphase. Historisch beste Einstiegszone."
        elif arc < 50:
            phase_label = "Mid Bull"
            phase_desc = "Expansion. Strukturelles Risiko kontrollierbar."
        elif arc < 65:
            phase_label = "Late Bull"
            phase_desc = "Spaetphase. Risiko steigt. Vorsicht."
        elif arc < 80:
            phase_label = "Distribution"
            phase_desc = "Verteilung. Positionen reduzieren."
        else:
            phase_label = "Bear / Risk Off"
            phase_desc = "Maximales Risiko. Kapitalerhalt."

    phase_scenarios = {
        "Early Bull":             {"upside": (25, 60),  "downside": (8, 20)},
        "Mid Bull":               {"upside": (15, 40),  "downside": (10, 25)},
        "Late Bull":              {"upside": (10, 25),  "downside": (15, 35)},
        "Distribution":           {"upside": (5, 15),   "downside": (20, 45)},
        "Bear / Risk Off":        {"upside": (5, 20),   "downside": (25, 55)},
        "Late Bear":              {"upside": (10, 30),  "downside": (15, 30)},
        "Late Bear / Accumulation": {"upside": (15, 40), "downside": (10, 25)},
        "Early Bear":             {"upside": (5, 20),   "downside": (20, 50)},
        "Transition":             {"upside": (8, 20),   "downside": (10, 25)},
    }
    scenario = phase_scenarios.get(phase_label, phase_scenarios["Transition"])

    score_factor = (st_score - 50) / 100.0
    up_low, up_high = scenario["upside"]
    dn_low, dn_high = scenario["downside"]
    upside_pct = round(up_high - (up_high - up_low) * (score_factor + 0.5))
    downside_pct = round(dn_low + (dn_high - dn_low) * (score_factor + 0.5))
    upside_pct = max(3, min(100, upside_pct))
    downside_pct = max(3, min(80, downside_pct))

    upside_target = round(price * (1 + upside_pct / 100)) if price > 0 else None
    downside_target = round(price * (1 - downside_pct / 100)) if price > 0 else None

    if st_score < 30:
        tactical = "OVERSOLD"
        tactical_color = "green"
    elif st_score < 45:
        tactical = "CAUTIOUS LONG"
        tactical_color = "green"
    elif st_score < 55:
        tactical = "NEUTRAL"
        tactical_color = "blue"
    elif st_score < 70:
        tactical = "CAUTION"
        tactical_color = "orange"
    else:
        tactical = "OVERBOUGHT"
        tactical_color = "red"

    return {
        "st_score": st_score,
        "phase_label": phase_label,
        "phase_desc": phase_desc,
        "upside_pct": upside_pct,
        "downside_pct": downside_pct,
        "upside_target": upside_target,
        "downside_target": downside_target,
        "tactical_signal": tactical,
        "tactical_color": tactical_color,
        "days_since_bottom": days,
        "days_since_top": days_since_top,
        "cycle_top_date": "2025-10-06",
    }


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

def _lerp(a, b, t):
    """Linear interpolation."""
    return a + (b - a) * _clamp(t, 0.0, 1.0)


# -----------------------------------------------------------------------------
# PART 1 - CYCLE PHASE MODEL
# -----------------------------------------------------------------------------

CYCLE_PHASES = [
    (0,  10,  "Capitulation",    "Peak fear and forced selling. Weakest hands exit."),
    (10, 20,  "Bottom Formation","Price stabilising. Volume drying up. Smart money watching."),
    (20, 30,  "Accumulation",    "Institutional accumulation. Low sentiment. Quiet building."),
    (30, 40,  "Early Bull",      "Trend reversal confirmed. Momentum building. Sentiment improving."),
    (40, 55,  "Bull Expansion",  "Broad participation. Liquidity expanding. Altcoins waking up."),
    (55, 70,  "Late Bull",       "Retail FOMO driving final leg. Leverage elevated. Risk rising."),
    (70, 80,  "Distribution",    "Smart money distributing. High sentiment. Divergences appearing."),
    (80, 90,  "Early Bear",      "Trend broken. Liquidity tightening. Bounces sold into."),
    (90, 100, "Late Bear",       "Capitulation approaching. Sentiment deeply negative."),
]

def _get_cycle_phase(position: float) -> tuple:
    """Return (phase_name, phase_description) for a 0–100 cycle position."""
    pos = _clamp(position)
    for lo, hi, name, desc in CYCLE_PHASES:
        if lo <= pos < hi:
            return name, desc
    return CYCLE_PHASES[-1][2], CYCLE_PHASES[-1][3]


def _compute_cycle_position(
    combined_score: float,
    btc_score: float,
    fear_greed: float,
    btc_drawdown_pct: float,   # negative number, e.g. -30.5
    macro_score: float,
    score_history: list,       # list of {"t": ms, "v": score}
) -> float:
    """
    Compute a refined 0–100 cycle position by blending multiple signals.
    Uses score momentum, drawdown depth, and sentiment.
    """
    combined = _clamp(_sf(combined_score, 50.0))
    btc      = _clamp(_sf(btc_score,      50.0))
    fg       = _clamp(_sf(fear_greed,     50.0))
    macro    = _clamp(_sf(macro_score,    50.0))
    dd       = _sf(btc_drawdown_pct, -30.0)

    # Drawdown → positional hint (deep drawdown = early cycle)
    # -80%+ = 0-10, -50% = 15-25, -20% = 35-45, 0% = 65-75
    dd_clamped = max(-100.0, min(0.0, dd))
    dd_position = 100.0 + dd_clamped  # -80% → 20, 0% → 100
    dd_score = _clamp(dd_position * 0.75)  # scale to 0-75 range

    # Score momentum (is the cycle accelerating or decelerating?)
    momentum_adj = 0.0
    if len(score_history) >= 10:
        try:
            recent   = [_sf(h["v"]) for h in score_history[-5:]]
            previous = [_sf(h["v"]) for h in score_history[-10:-5]]
            recent_mean   = sum(recent)   / len(recent)
            previous_mean = sum(previous) / len(previous)
            momentum_adj = (recent_mean - previous_mean) * 0.3
        except:
            pass

    # Weighted blend
    raw_position = (
        combined * 0.40 +
        btc      * 0.25 +
        fg       * 0.15 +
        macro    * 0.10 +
        dd_score * 0.10
    ) + momentum_adj

    return _clamp(raw_position)


# ─────────────────────────────────────────────────────────────────────────────
# ALPHA CYCLE POSITION SCORE
# 0 = cycle bottom (maximum opportunity) | 100 = cycle top (maximum risk)
# Weights: 35% MA-200W | 25% Drawdown from ATH | 20% Fear&Greed | 20% Liquidity
# ─────────────────────────────────────────────────────────────────────────────

def _compute_alpha_cycle_position(
    btc_price:       float,
    ma_200w:         float,
    ath_price:       float,
    fear_greed:      float,
    liquidity_score: float,
) -> float:
    """
    Proper weighted AlphaCycle Position Score.
    Replaces the bugged 100% output from _compute_cycle_position.

    Returns float 0.0–100.0.
    0  = deep cycle bottom (extreme opportunity)
    100 = cycle top (extreme risk)
    """
    price = _sf(btc_price,   50000.0)
    ma    = _sf(ma_200w,     40000.0)
    ath   = _sf(ath_price,   max(price, 1.0))
    fg    = _clamp(_sf(fear_greed,      50.0))
    liq   = _clamp(_sf(liquidity_score, 50.0))

    # Guard: if ath is 0 or less than price, use price as ath
    if ath <= 0 or ath < price:
        ath = price

    # ── Component 1: Price vs 200-Week MA (weight: 35%) ──────────────────────
    # deviation: negative = below MA (bottom zone), positive = above MA (top zone)
    if ma > 0:
        deviation = (price - ma) / ma
    else:
        deviation = 0.0

    # Normalize deviation → 0–100
    # -100% below MA → 0 (extreme bottom)
    #    0% at MA     → 40 (neutral-low)
    #  +100% above MA → 75
    #  +300% above MA → 100 (extreme top, like 2021)
    if deviation <= -1.0:
        ma_score = 0.0
    elif deviation < 0.0:
        ma_score = _clamp(40.0 + deviation * 40.0)
    elif deviation < 1.0:
        ma_score = _clamp(40.0 + deviation * 35.0)
    elif deviation < 3.0:
        ma_score = _clamp(75.0 + (deviation - 1.0) * 12.5)
    else:
        ma_score = 100.0

    # ── Component 2: Drawdown from ATH (weight: 25%) ─────────────────────────
    # drawdown = 0.0 at ATH, 1.0 = total loss
    drawdown = _clamp((ath - price) / ath, 0.0, 1.0)

    # High drawdown → LOW score (near bottom)
    # Low drawdown  → HIGH score (near top)
    # 0% DD (at ATH) → 100
    # 30% DD         → ~55
    # 50% DD         → ~25
    # 80%+ DD        → ~0
    drawdown_score = _clamp((1.0 - drawdown) ** 1.5 * 100.0)

    # ── Component 3: Fear & Greed / Sentiment (weight: 20%) ──────────────────
    # Direct use: 0=Extreme Fear (bottom), 100=Extreme Greed (top)
    sentiment_score = fg

    # ── Component 4: Liquidity Score (weight: 20%) ────────────────────────────
    # Direct use: already normalized 0–100
    # NOTE: macro_score from scoring.py is passed here.
    # Low macro score = tight liquidity = early cycle = LOW position score
    # High macro score = easy liquidity = late cycle = HIGH position score
    liquidity_final = liq

    # ── Weighted Final Score ──────────────────────────────────────────────────
    score = (
        ma_score        * 0.35 +
        drawdown_score  * 0.25 +
        sentiment_score * 0.20 +
        liquidity_final * 0.20
    )

    return round(_clamp(score), 1)


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 — WALL STREET PSYCHOLOGY MODEL
# ─────────────────────────────────────────────────────────────────────────────

PSYCHOLOGY_MAP = [
    (0,   8,   "Capitulation",  "Maximum Pain"),
    (8,   15,  "Anger",         "Blow-Off Bottom"),
    (15,  22,  "Depression",    "Prolonged Despair"),
    (22,  30,  "Disbelief",     "Dead Cat Bounce"),
    (30,  38,  "Hope",          "Early Recovery"),
    (38,  46,  "Optimism",      "Trend Confirmation"),
    (46,  55,  "Belief",        "Momentum Phase"),
    (55,  63,  "Thrill",        "Institutional FOMO"),
    (63,  71,  "Euphoria",      "Retail Mania"),
    (71,  78,  "Complacency",   "False Security"),
    (78,  85,  "Anxiety",       "First Cracks"),
    (85,  92,  "Denial",        "Bull Trap"),
    (92,  101, "Panic",         "Forced Liquidation"),
]

def _get_psychology(position: float) -> tuple:
    """Return (psychology_phase, wall_street_phase)."""
    pos = _clamp(position)
    for lo, hi, psych, ws in PSYCHOLOGY_MAP:
        if lo <= pos < hi:
            return psych, ws
    return "Capitulation", "Maximum Pain"


# ─────────────────────────────────────────────────────────────────────────────
# PART 3 — SEASONALITY ENGINE (SEASONAX STYLE)
# ─────────────────────────────────────────────────────────────────────────────

# Monthly Bitcoin historical performance bias (0=very bearish, 100=very bullish)
# Based on 10+ years of Bitcoin monthly return distribution
MONTHLY_BIAS = {
    1:  62,   # January  — post-holiday recovery, often strong
    2:  58,   # February — historically decent
    3:  52,   # March    — mixed, sometimes turbulent (tax season)
    4:  65,   # April    — historically strong, Q2 start
    5:  60,   # May      — "Sell in May" effect muted in crypto
    6:  45,   # June     — often weak
    7:  42,   # July     — weakest summer month
    8:  48,   # August   — mixed
    9:  38,   # September— historically weakest month ("Septembear")
    10: 72,   # October  — "Uptober", historically very strong
    11: 75,   # November — historically strongest month
    12: 68,   # December — generally strong, holiday rally
}

QUARTERLY_BIAS = {
    1: (50, "Q1 Recovery",          "Mixed recovery from year-end. Institutional positioning."),
    2: (62, "Q2 Bull Season",        "Historically bullish quarter. Spring accumulation phase."),
    3: (42, "Q3 Summer Weakness",    "Historically weakest quarter. Low volume, summer doldrums."),
    4: (72, "Q4 Year-End Rally",     "Historically strongest quarter. Bull season peak."),
}

# Bitcoin halving dates (approximate)
HALVING_DATES = [
    datetime(2012, 11, 28),
    datetime(2016, 7, 9),
    datetime(2020, 5, 11),
    datetime(2024, 4, 19),   # Most recent
]

def _get_halving_year(now: datetime) -> tuple:
    """
    Return (years_since_halving, halving_year_label, halving_bias_score, halving_phase).
    Halving cycle:
      Year 0–1  (0-12m):  Accumulation/Pre-bull
      Year 1–2  (12-24m): Bull Expansion (strongest)
      Year 2–3  (24-36m): Late Bull / Distribution
      Year 3–4  (36-48m): Bear Market
    """
    latest_halving = max(h for h in HALVING_DATES if h <= now)
    months_since = (now.year - latest_halving.year) * 12 + (now.month - latest_halving.month)
    years_since  = months_since / 12.0

    if months_since < 6:
        return years_since, "Pre-Halving Accumulation", 58, "Post-Halving Accumulation"
    elif months_since < 12:
        return years_since, "Year 1 Post-Halving (Early)", 65, "Post-Halving Expansion"
    elif months_since < 18:
        return years_since, "Year 1 Post-Halving (Peak)", 78, "Post-Halving Bull Phase"
    elif months_since < 24:
        return years_since, "Year 2 Post-Halving (Late Bull)", 68, "Late Bull Distribution Window"
    elif months_since < 30:
        return years_since, "Year 2 Post-Halving (Top Zone)", 55, "Cycle Top Formation Window"
    elif months_since < 36:
        return years_since, "Year 3 Post-Halving (Early Bear)", 35, "Bear Market Season"
    elif months_since < 42:
        return years_since, "Year 3 Post-Halving (Deep Bear)", 22, "Bear Market Bottom Zone"
    else:
        return years_since, "Year 4 Post-Halving (Accumulation)", 48, "Accumulation Season"


def _compute_seasonality(now: datetime) -> dict:
    """
    Compute full seasonality analysis.
    Returns score 0-100, bias label, phase, and component breakdown.
    """
    month   = now.month
    quarter = (month - 1) // 3 + 1

    monthly_score  = _sf(MONTHLY_BIAS.get(month, 50), 50.0)
    q_score, q_label, q_desc = QUARTERLY_BIAS.get(quarter, (50, "Neutral", "No strong seasonal bias."))
    years_since, halving_label, halving_score, halving_phase = _get_halving_year(now)

    # Month name
    month_names = ["","January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
    month_name = month_names[month]

    # Weighted seasonality score
    seasonality_score = _clamp(
        monthly_score  * 0.35 +
        q_score        * 0.30 +
        halving_score  * 0.35
    )

    # Bias label
    if seasonality_score >= 65:
        bias = "BULLISH"
    elif seasonality_score <= 40:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    # Seasonality phase (composite label)
    if halving_score >= 70 and monthly_score >= 65:
        seasonality_phase = halving_phase + " — Strong Seasonal Tailwind"
    elif halving_score <= 35:
        seasonality_phase = halving_phase
    elif bias == "BEARISH":
        seasonality_phase = f"{halving_phase} — Seasonal Headwind"
    else:
        seasonality_phase = halving_phase

    return {
        "seasonality_score":  round(seasonality_score, 1),
        "seasonality_bias":   bias,
        "seasonality_phase":  seasonality_phase,
        "month_name":         month_name,
        "month_score":        monthly_score,
        "quarter_label":      q_label,
        "quarter_score":      q_score,
        "quarter_desc":       q_desc,
        "halving_label":      halving_label,
        "halving_score":      halving_score,
        "halving_phase":      halving_phase,
        "years_since_halving": round(years_since, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PART 4 — PROBABILITY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_probabilities(
    cycle_position:    float,
    seasonality_score: float,
    fear_greed:        float,
    macro_score:       float,
    btc_drawdown_pct:  float,
) -> tuple:
    """
    Compute bottom_probability and top_probability (0–100 each).
    These are NOT mutually exclusive — both can be low in the middle of a cycle.
    """
    pos  = _clamp(cycle_position)
    seas = _clamp(seasonality_score)
    fg   = _clamp(_sf(fear_greed, 50.0))
    mac  = _clamp(_sf(macro_score, 50.0))
    dd   = _sf(btc_drawdown_pct, -30.0)

    # ── BOTTOM PROBABILITY
    # High when: low cycle position, extreme fear, deep drawdown, tight macro
    bottom_signals = []

    # Cycle position: lower = more likely near bottom
    if pos < 15:   bottom_signals.append(90.0)
    elif pos < 25: bottom_signals.append(70.0)
    elif pos < 35: bottom_signals.append(45.0)
    elif pos < 50: bottom_signals.append(20.0)
    else:          bottom_signals.append(max(0.0, 20.0 - (pos - 50) * 0.8))

    # Fear & Greed: extreme fear = near bottom
    if fg < 10:    bottom_signals.append(88.0)
    elif fg < 20:  bottom_signals.append(72.0)
    elif fg < 30:  bottom_signals.append(55.0)
    elif fg < 45:  bottom_signals.append(35.0)
    else:          bottom_signals.append(max(0.0, 35.0 - (fg - 45) * 0.8))

    # Drawdown depth
    dd_abs = abs(dd)
    if dd_abs >= 70:   bottom_signals.append(85.0)
    elif dd_abs >= 50: bottom_signals.append(65.0)
    elif dd_abs >= 30: bottom_signals.append(40.0)
    elif dd_abs >= 15: bottom_signals.append(20.0)
    else:              bottom_signals.append(5.0)

    # Macro (tight macro = near bottom)
    if mac > 70:   bottom_signals.append(60.0)
    elif mac > 55: bottom_signals.append(40.0)
    elif mac > 40: bottom_signals.append(20.0)
    else:          bottom_signals.append(10.0)

    # Seasonality boost
    seas_adj = (seas - 50.0) * 0.2   # -10 to +10 adjustment

    bottom_prob = _clamp(sum(bottom_signals) / len(bottom_signals) + seas_adj)

    # ── TOP PROBABILITY
    # High when: high cycle position, extreme greed, small drawdown, easy macro
    top_signals = []

    if pos >= 85:  top_signals.append(90.0)
    elif pos >= 70: top_signals.append(72.0)
    elif pos >= 60: top_signals.append(55.0)
    elif pos >= 50: top_signals.append(35.0)
    else:           top_signals.append(max(0.0, 35.0 - (50.0 - pos) * 0.7))

    # Fear & Greed: extreme greed = near top
    if fg >= 90:   top_signals.append(88.0)
    elif fg >= 75: top_signals.append(70.0)
    elif fg >= 60: top_signals.append(50.0)
    elif fg >= 50: top_signals.append(30.0)
    else:          top_signals.append(max(0.0, 30.0 - (50.0 - fg) * 0.6))

    # Drawdown (near ATH = more likely near top)
    if dd_abs < 5:   top_signals.append(85.0)
    elif dd_abs < 15: top_signals.append(65.0)
    elif dd_abs < 30: top_signals.append(40.0)
    elif dd_abs < 50: top_signals.append(20.0)
    else:             top_signals.append(5.0)

    # Macro (loose macro = risk of blow-off top)
    if mac < 30:   top_signals.append(65.0)
    elif mac < 45: top_signals.append(45.0)
    elif mac < 55: top_signals.append(25.0)
    else:          top_signals.append(10.0)

    # Seasonal headwind = lower top probability
    seas_top_adj = -(seas - 50.0) * 0.15

    top_prob = _clamp(sum(top_signals) / len(top_signals) + seas_top_adj)

    return round(bottom_prob, 1), round(top_prob, 1)


# ─────────────────────────────────────────────────────────────────────────────
# PART 5 — FORECAST ENGINE
# ─────────────────────────────────────────────────────────────────────────────

NEXT_PHASE_MAP = [
    (0,  15,  "Bottom Formation",        "First signs of price stabilisation"),
    (15, 25,  "Accumulation Phase",      "Quiet accumulation. Volume drying up"),
    (25, 38,  "Early Bull Phase",        "Trend reversal. Breakout above key levels"),
    (38, 52,  "Bull Expansion Phase",    "Broad market rally. Altcoins activating"),
    (52, 65,  "Late Bull Phase",         "Final parabolic leg. Leverage spike"),
    (65, 75,  "Cycle Top Formation",     "Distribution window opening"),
    (75, 85,  "Early Bear Phase",        "Trend breakdown confirmed"),
    (85, 95,  "Deep Bear Phase",         "Capitulation event approaching"),
    (95, 101, "Capitulation Bottom",     "Maximum pain. Cycle low forming"),
]

MAJOR_EVENTS = {
    "Capitulation":      "Cascade liquidation event / final flush",
    "Bottom Formation":  "First accumulation by institutional buyers",
    "Accumulation":      "Breakout above 200-week moving average",
    "Early Bull":        "First major higher high — trend confirmed",
    "Bull Expansion":    "Altcoin season initiation",
    "Late Bull":         "Cycle Top Formation Window (parabolic peak)",
    "Distribution":      "Lower high formation — first technical warning",
    "Early Bear":        "Bear market rally trap (bull trap)",
    "Late Bear":         "Capitulation event — final selling",
}

def _get_forecast(cycle_position: float, current_phase: str) -> tuple:
    pos = _clamp(cycle_position)
    next_phase = "Accumulation Phase"
    for lo, hi, phase, _ in NEXT_PHASE_MAP:
        if lo <= pos < hi:
            next_phase = phase
            break

    major_event = MAJOR_EVENTS.get(current_phase, "Key technical level test")
    return next_phase, major_event


# ─────────────────────────────────────────────────────────────────────────────
# PART 6 — SIGNAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_signal(
    cycle_position:    float,
    bottom_prob:       float,
    top_prob:          float,
    seasonality_score: float,
    fear_greed:        float,
    macro_score:       float,
) -> str:
    pos   = _clamp(cycle_position)
    s_scr = _clamp(seasonality_score)
    fg    = _clamp(_sf(fear_greed, 50.0))
    bp    = _clamp(bottom_prob)
    tp    = _clamp(top_prob)
    mac   = _clamp(_sf(macro_score, 50.0))

    # Composite buy/sell signal score (0=strong sell, 100=strong buy)
    signal_score = (
        (100.0 - pos)    * 0.35 +   # low cycle position = buy
        bp               * 0.25 +   # high bottom prob = buy
        (100.0 - tp)     * 0.20 +   # low top prob = buy
        (100.0 - fg)     * 0.10 +   # low fear/greed = buy
        s_scr            * 0.05 +   # seasonal tailwind = buy
        (100.0 - mac)    * 0.05     # tight macro = not sell yet
    )
    signal_score = _clamp(signal_score)

    if signal_score >= 78:   return "STRONG_BUY"
    elif signal_score >= 62: return "BUY"
    elif signal_score >= 42: return "HOLD"
    elif signal_score >= 28: return "SELL"
    else:                    return "STRONG_SELL"


# ─────────────────────────────────────────────────────────────────────────────
# PART 7 — RISK ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_risk(
    cycle_position:   float,
    top_prob:         float,
    fear_greed:       float,
    macro_score:      float,
    seasonality_score:float,
) -> str:
    pos  = _clamp(cycle_position)
    tp   = _clamp(top_prob)
    fg   = _clamp(_sf(fear_greed, 50.0))
    mac  = _clamp(_sf(macro_score, 50.0))
    seas = _clamp(seasonality_score)

    # Risk score: higher = more risky
    risk_score = (
        pos   * 0.35 +
        tp    * 0.25 +
        fg    * 0.20 +
        mac   * 0.10 +
        (100.0 - seas) * 0.10
    )
    risk_score = _clamp(risk_score)

    if risk_score >= 72:   return "EXTREME"
    elif risk_score >= 55: return "HIGH"
    elif risk_score >= 38: return "MEDIUM"
    else:                  return "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# PART 8 — CONFIDENCE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_confidence(
    combined_score:    float,
    btc_score:         float,
    macro_score:       float,
    seasonality_score: float,
    score_history:     list,
) -> float:
    """
    Confidence in current reading.
    Increases when: multiple signals agree, consistent history, strong seasonality conviction.
    Decreases when: signals diverging, short history, mixed seasonality.
    """
    combined = _sf(combined_score, 50.0)
    btc      = _sf(btc_score, 50.0)
    macro    = _sf(macro_score, 50.0)
    seas     = _sf(seasonality_score, 50.0)

    # Signal agreement (all three pointing same direction = high confidence)
    signals = [combined, btc, macro]
    signal_mean = sum(signals) / 3.0
    signal_divergence = sum(abs(s - signal_mean) for s in signals) / 3.0

    # Lower divergence = higher confidence
    agreement_score = _clamp(100.0 - signal_divergence * 2.0)

    # History depth bonus
    history_depth = min(len(score_history), 100)
    history_bonus = history_depth * 0.2  # max 20 points

    # Seasonality conviction (extreme scores = higher confidence)
    seas_conviction = abs(seas - 50.0) * 1.2  # max ~60

    # Trend clarity (how far from 50 = more decisive signal = higher confidence)
    trend_clarity = abs(combined - 50.0) * 0.8

    raw_confidence = (
        agreement_score * 0.40 +
        _clamp(50.0 + trend_clarity)     * 0.25 +
        _clamp(40.0 + seas_conviction)   * 0.20 +
        _clamp(30.0 + history_bonus)     * 0.15
    )

    return round(_clamp(raw_confidence, 20.0, 95.0), 1)


# ─────────────────────────────────────────────────────────────────────────────
# PART 9 — SUMMARY GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def _institutional_summary(
    phase:            str,
    cycle_position:   float,
    signal:           str,
    risk_level:       str,
    seasonality:      dict,
    bottom_prob:      float,
    top_prob:         float,
    macro_score:      float,
    fear_greed:       float,
) -> str:
    pos  = round(_clamp(cycle_position), 1)
    seas = seasonality.get("seasonality_bias", "NEUTRAL")
    hal  = seasonality.get("halving_label", "")
    mac  = _sf(macro_score, 50.0)
    fg   = _sf(fear_greed,  50.0)

    # Liquidity context
    if mac < 35:
        liq_context = "Macro liquidity is restrictive — risk premium elevated."
    elif mac < 50:
        liq_context = "Macro liquidity contracting — headwinds present."
    elif mac < 65:
        liq_context = "Macro liquidity neutral — no strong directional bias."
    else:
        liq_context = "Macro liquidity expanding — structural tailwind in place."

    # Seasonal context
    if seas == "BULLISH":
        seas_context = f"Seasonal analysis confirms tailwind ({hal}). Historical bias favors upside."
    elif seas == "BEARISH":
        seas_context = f"Seasonal headwind present ({hal}). Historical bias unfavorable near-term."
    else:
        seas_context = f"Seasonal positioning neutral ({hal}). No strong historical directional bias."

    # Positioning context
    if cycle_position < 25:
        pos_context  = f"Cycle positioned at {pos}/100 — deep accumulation zone. Bottom probability: {bottom_prob}%."
        ra_context   = "Risk/reward asymmetric to upside at current levels."
    elif cycle_position < 45:
        pos_context  = f"Cycle positioned at {pos}/100 — early expansion phase. Trend structure improving."
        ra_context   = "Risk/reward favourable. Position sizing can be increased on confirmation."
    elif cycle_position < 65:
        pos_context  = f"Cycle positioned at {pos}/100 — mid-cycle bull market. Momentum phase."
        ra_context   = "Risk/reward neutral. Maintain core positions. Reduce leverage."
    elif cycle_position < 80:
        pos_context  = f"Cycle positioned at {pos}/100 — late cycle distribution zone. Top probability: {top_prob}%."
        ra_context   = "Risk/reward deteriorating. Reduce exposure. Take partial profits."
    else:
        pos_context  = f"Cycle positioned at {pos}/100 — bear market territory. Preservation priority."
        ra_context   = "Risk/reward unfavorable. Capital preservation is primary objective."

    # Sentiment
    if fg < 15:
        sent_context = f"Market sentiment at extreme fear ({fg:.0f}/100) — historically high-conviction buy signal."
    elif fg < 30:
        sent_context = f"Market sentiment deeply negative ({fg:.0f}/100) — contrarian setup developing."
    elif fg > 80:
        sent_context = f"Market sentiment at extreme greed ({fg:.0f}/100) — distribution risk elevated."
    elif fg > 65:
        sent_context = f"Market sentiment elevated ({fg:.0f}/100) — caution warranted."
    else:
        sent_context = f"Market sentiment neutral ({fg:.0f}/100) — no extreme reading."

    return (
        f"{pos_context} "
        f"{liq_context} "
        f"{seas_context} "
        f"{sent_context} "
        f"{ra_context}"
    )


def _retail_summary(
    phase:          str,
    signal:         str,
    risk_level:     str,
    cycle_position: float,
    fear_greed:     float,
    bottom_prob:    float,
) -> str:
    fg  = _sf(fear_greed, 50.0)
    pos = _clamp(cycle_position)

    summaries = {
        "STRONG_BUY": (
            f"Market is in {phase} — historically a strong buying opportunity. "
            f"Fear is extreme ({fg:.0f}/100), which has historically marked major lows. "
            f"Bottom probability: {bottom_prob}%. This is when long-term investors accumulate."
        ),
        "BUY": (
            f"Market is in {phase} — conditions favoring buyers. "
            f"Cycle score is low at {pos:.0f}/100. "
            f"Good opportunity to build positions gradually."
        ),
        "HOLD": (
            f"Market is in {phase} — mid-cycle positioning. "
            f"No extreme readings in either direction. "
            f"Hold existing positions. Avoid adding on leverage."
        ),
        "SELL": (
            f"Market is in {phase} — risk increasing. "
            f"Cycle score at {pos:.0f}/100. "
            f"Consider reducing position size and taking some profits."
        ),
        "STRONG_SELL": (
            f"Market is in {phase} — high-risk zone. "
            f"Cycle score elevated at {pos:.0f}/100. "
            f"Protect capital. Reduce exposure significantly."
        ),
    }
    return summaries.get(signal, f"Market in {phase}. Monitor key levels closely.")


# ─────────────────────────────────────────────────────────────────────────────
# PART 10 — STRATEGY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_MAP = {
    "STRONG_BUY":  "Accumulate aggressively",
    "BUY":         "Accumulate",
    "HOLD":        "Hold",
    "SELL":        "Reduce exposure",
    "STRONG_SELL": "Exit positions",
}


# -----------------------------------------------------------------------------
# MAIN ANALYZER CLASS
# -----------------------------------------------------------------------------

class CycleAnalyzer:
    """
    Institutional-grade Bitcoin/Crypto Cycle Analyzer.
    All methods are stateless and pure. Zero NaN guarantee.
    """

    def analyze(
        self,
        combined_score:    float,
        btc_score:         float,
        eth_score:         float,
        macro_score:       float,
        fear_greed:        float,
        btc_price:         float,
        btc_drawdown_pct:  float,      # e.g. -31.8
        liquidity_trend:   float,      # macro liquidity score 0-100
        score_history:     list,       # [{"t": ms, "v": score}, ...]
        btc_price_history: list,       # list of float prices
        ma_200w:           float = 0.0,
        ath_price:         float = 0.0,
        now:               Optional[datetime] = None,
    ) -> dict:
        """
        Run full institutional cycle analysis.
        Returns complete analyzer output dict. Never raises. Never returns NaN.
        """
        if now is None:
            now = datetime.utcnow()

        try:
            return self._run(
                _sf(combined_score, 50.0),
                _sf(btc_score,      50.0),
                _sf(eth_score,      50.0),
                _sf(macro_score,    50.0),
                _sf(fear_greed,     50.0),
                _sf(btc_price,      0.0),
                _sf(btc_drawdown_pct, -30.0),
                _sf(liquidity_trend,  50.0),
                score_history      or [],
                btc_price_history  or [],
                now,
                ma_200w   = _sf(ma_200w,   0.0),
                ath_price = _sf(ath_price, 0.0),
            )
        except Exception as e:
            logger.error(f"CycleAnalyzer.analyze failed: {e}", exc_info=True)
            return self._fallback_output(now)

    def _run(self, combined, btc, eth, macro, fg, price, dd, liq_trend,
             history, price_history, now,
             ma_200w=0.0, ath_price=0.0) -> dict:

        # ── 1. Cycle Position
        cycle_position = _compute_cycle_position(
            combined, btc, fg, dd, macro, history
        )
        phase, phase_desc = _get_cycle_phase(cycle_position)

        # ── 1b. AlphaCycle Position Score (corrected weighted model)
        alpha_cycle_position = _compute_alpha_cycle_position(
            btc_price       = price,
            ma_200w         = ma_200w,
            ath_price       = ath_price,
            fear_greed      = fg,
            liquidity_score = macro,
        )

        # ── 2. Psychology
        psychology_phase, wall_street_phase = _get_psychology(cycle_position)

        # ── 3. Seasonality
        seasonality = _compute_seasonality(now)

        # ── 4. Probabilities
        bottom_prob, top_prob = _compute_probabilities(
            cycle_position,
            seasonality["seasonality_score"],
            fg, macro, dd
        )

        # ── 5. Forecast
        next_phase, next_event = _get_forecast(cycle_position, phase)

        # ── 6. Signal
        signal = _compute_signal(
            cycle_position, bottom_prob, top_prob,
            seasonality["seasonality_score"], fg, macro
        )

        # ── 7. Risk
        risk_level = _compute_risk(
            cycle_position, top_prob, fg, macro,
            seasonality["seasonality_score"]
        )

        # ── 8. Confidence
        confidence = _compute_confidence(combined, btc, macro,
                                         seasonality["seasonality_score"], history)

        # ── 9. Summaries
        institutional_summary = _institutional_summary(
            phase, cycle_position, signal, risk_level,
            seasonality, bottom_prob, top_prob, macro, fg
        )
        retail_summary = _retail_summary(
            phase, signal, risk_level, cycle_position, fg, bottom_prob
        )

        # ── 10. Strategy
        strategy = STRATEGY_MAP.get(signal, "Hold")

        result = {
            # Core
            "phase":                   phase,
            "phase_description":       phase_desc,
            "cycle_position_percent":  round(cycle_position, 1),
            "alpha_cycle_position":    alpha_cycle_position,

            # Psychology
            "psychology_phase":        psychology_phase,
            "wall_street_phase":       wall_street_phase,

            # Seasonality
            "seasonality_phase":       seasonality["seasonality_phase"],
            "seasonality_score":       seasonality["seasonality_score"],
            "seasonality_bias":        seasonality["seasonality_bias"],
            "seasonality_detail": {
                "month":               seasonality["month_name"],
                "month_score":         seasonality["month_score"],
                "quarter":             seasonality["quarter_label"],
                "quarter_score":       seasonality["quarter_score"],
                "quarter_description": seasonality["quarter_desc"],
                "halving_cycle":       seasonality["halving_label"],
                "halving_score":       seasonality["halving_score"],
                "years_since_halving": seasonality["years_since_halving"],
            },

            # Probabilities
            "bottom_probability":      bottom_prob,
            "top_probability":         top_prob,

            # Forecast
            "expected_next_phase":       next_phase,
            "expected_next_major_event": next_event,

            # Signal & Risk
            "signal":      signal,
            "risk_level":  risk_level,
            "confidence":  confidence,

            # Narratives
            "institutional_summary": institutional_summary,
            "retail_summary":        retail_summary,
            "strategy":              strategy,

            # Input scores (for transparency)
            "input_scores": {
                "combined": round(combined, 1),
                "btc":      round(btc,      1),
                "eth":      round(eth,      1),
                "macro":    round(macro,    1),
                "fear_greed": round(fg,     1),
            },
        }

        # Cycle Signal Detection (Top/Bottom)
        try:
            _arc = result.get("alpha_cycle_position", 50.0)
            _dd_raw = _sf(dd, -30.0)
            _dd = abs(_dd_raw) / 100.0 if _dd_raw < 0 else 0.0
            if _dd > 1.0:
                _dd = 1.0
            _fg = result.get("input_scores", {}).get("fear_greed", 50.0)
            _rsi = 50.0
            _liq = result.get("input_scores", {}).get("macro", 50.0)
            _fund = 50.0
            _price = _sf(price, 0.0)
            _ma200w = _sf(ma_200w, 0.0)

            cycle_signal = detect_cycle_signal(
                arc_score=_arc,
                drawdown_pct=_dd,
                fear_greed=_fg,
                rsi_weekly=_rsi,
                liquidity_score=_liq,
                funding_score=_fund,
                price=_price,
                ma_200w=_ma200w,
            )
            result["cycle_signal"] = cycle_signal
            override = cycle_signal.get("decision_override")
            if override:
                result["decision_override"] = override
                result["position"] = override
        except Exception as e:
            logger.warning("cycle_signal detection failed: %s", e)
            result["cycle_signal"] = {
                "signal_type": "NONE",
                "signal_strength": 0,
                "error": str(e),
            }

        # ARC Momentum + Percentile (from score history)
        try:
            arc_hist = [
                {"date": datetime.utcfromtimestamp(h["t"] / 1000).strftime("%Y-%m-%d"), "arc_score": h["v"]}
                for h in (history or [])
                if isinstance(h, dict) and h.get("t") is not None and h.get("v") is not None
            ]
            current_arc = result.get("alpha_cycle_position", 50.0)
            momentum_data = compute_arc_momentum(arc_hist, current_arc)
            result.update(momentum_data)
        except Exception as e:
            logger.warning("momentum error: %s", e)
            result["arc_momentum_30d"] = None
            result["arc_momentum_label"] = "N/A"
            result["arc_percentile"] = None
            result["arc_percentile_label"] = "N/A"

        return result

    @staticmethod
    def _fallback_output(now: datetime) -> dict:
        """Emergency fallback — never raises, never returns NaN."""
        seas = _compute_seasonality(now)
        return {
            "phase":                   "Accumulation",
            "phase_description":       "Data loading. Retry in 30 seconds.",
            "cycle_position_percent":  50.0,
            "alpha_cycle_position":    50.0,
            "psychology_phase":        "Disbelief",
            "wall_street_phase":       "Dead Cat Bounce",
            "seasonality_phase":       seas["seasonality_phase"],
            "seasonality_score":       seas["seasonality_score"],
            "seasonality_bias":        seas["seasonality_bias"],
            "seasonality_detail": {
                "month":               seas["month_name"],
                "month_score":         seas["month_score"],
                "quarter":             seas["quarter_label"],
                "quarter_score":       seas["quarter_score"],
                "quarter_description": seas["quarter_desc"],
                "halving_cycle":       seas["halving_label"],
                "halving_score":       seas["halving_score"],
                "years_since_halving": seas["years_since_halving"],
            },
            "bottom_probability":        50.0,
            "top_probability":           10.0,
            "expected_next_phase":       "Accumulation Phase",
            "expected_next_major_event": "Data loading",
            "signal":                    "HOLD",
            "risk_level":                "MEDIUM",
            "confidence":                20.0,
            "institutional_summary":     "Awaiting data. Analysis will update on next cache refresh.",
            "retail_summary":            "Data loading. Check back in 30 seconds.",
            "strategy":                  "Hold",
            "input_scores": {
                "combined": 50.0, "btc": 50.0, "eth": 50.0,
                "macro": 50.0, "fear_greed": 50.0,
            },
            "cycle_signal": {
                "signal_type": "NONE",
                "signal_strength": 0,
                "description": "Data loading.",
            },
        }


# Module-level singleton
analyzer = CycleAnalyzer()
