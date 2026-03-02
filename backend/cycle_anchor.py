"""
cycle_anchor.py — Cycle Anchor Engine
Anchors the system to REAL historical Bitcoin cycle structure.
Deterministic, datetime-only. No randomness.
"""
from datetime import date, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# HARD-CODED HISTORICAL BITCOIN CYCLE DATA
# ─────────────────────────────────────────────────────────────────────────────

CYCLE_BOTTOMS: list[date] = [
    date(2015, 1, 14),
    date(2018, 12, 15),
    date(2022, 11, 21),
]

CYCLE_TOPS: list[date] = [
    date(2013, 12, 4),
    date(2017, 12, 17),
    date(2021, 11, 10),
    date(2025, 10, 25),  # estimated / reference
]

BITCOIN_HALVINGS: list[date] = [
    date(2012, 11, 28),
    date(2016, 7, 9),
    date(2020, 5, 11),
    date(2024, 4, 20),
]

# Current cycle anchor (we are in this cycle)
CURRENT_CYCLE_BOTTOM = date(2022, 11, 21)
LAST_HALVING = date(2024, 4, 20)

# Historical bottom → top durations (bull phase), in days
# 2015-01-14 → 2017-12-17,  2018-12-15 → 2021-11-10
BULL_PHASE_DAYS_1 = (date(2017, 12, 17) - date(2015, 1, 14)).days
BULL_PHASE_DAYS_2 = (date(2021, 11, 10) - date(2018, 12, 15)).days

# Historical top → next bottom (bear phase), in days
# 2017-12-17 → 2018-12-15,  2021-11-10 → 2022-11-21
BEAR_PHASE_DAYS_1 = (date(2018, 12, 15) - date(2017, 12, 17)).days
BEAR_PHASE_DAYS_2 = (date(2022, 11, 21) - date(2021, 11, 10)).days

# Averages (deterministic)
HISTORICAL_AVERAGE_BULL_DAYS = (BULL_PHASE_DAYS_1 + BULL_PHASE_DAYS_2) // 2
HISTORICAL_AVERAGE_BEAR_DAYS = (BEAR_PHASE_DAYS_1 + BEAR_PHASE_DAYS_2) // 2
HISTORICAL_AVERAGE_CYCLE_DAYS = HISTORICAL_AVERAGE_BULL_DAYS + HISTORICAL_AVERAGE_BEAR_DAYS

# Post-halving to cycle top (for halving_cycle_position)
# 2016-07-09 → 2017-12-17,  2020-05-11 → 2021-11-10
POST_HALVING_TO_TOP_1 = (date(2017, 12, 17) - date(2016, 7, 9)).days
POST_HALVING_TO_TOP_2 = (date(2021, 11, 10) - date(2020, 5, 11)).days
AVERAGE_POST_HALVING_TO_TOP_DAYS = (POST_HALVING_TO_TOP_1 + POST_HALVING_TO_TOP_2) // 2


def _clamp_pct(value: float) -> float:
    """Clamp to 0–100."""
    return max(0.0, min(100.0, value))


def compute_cycle_anchor(reference_date: date | None = None) -> dict:
    """
    Compute cycle anchor metrics. Deterministic.
    reference_date: defaults to today (UTC date); inject for tests.
    """
    today = reference_date or date.today()

    # Step 1 & 2: Current cycle, days since bottom
    days_since_bottom = (today - CURRENT_CYCLE_BOTTOM).days
    days_since_top: int | None = None  # we have not reached top yet

    # Step 3 & 4: Expected top date from average bull duration
    expected_top_date = CURRENT_CYCLE_BOTTOM + timedelta(days=HISTORICAL_AVERAGE_BULL_DAYS)
    expected_bottom_date = expected_top_date + timedelta(days=HISTORICAL_AVERAGE_BEAR_DAYS)

    # Step 5: cycle_position_percent (progress from bottom toward expected top)
    cycle_position_percent = (days_since_bottom / HISTORICAL_AVERAGE_BULL_DAYS) * 100.0
    cycle_position_percent = _clamp_pct(cycle_position_percent)

    # Step 6: days to next top / bottom
    days_to_next_top = (expected_top_date - today).days
    days_to_next_bottom = (expected_bottom_date - today).days

    # Step 7: Halving cycle position — days since last halving, relative to average post-halving cycle
    days_since_halving = (today - LAST_HALVING).days
    halving_cycle_position_percent = (days_since_halving / AVERAGE_POST_HALVING_TO_TOP_DAYS) * 100.0
    halving_cycle_position_percent = _clamp_pct(halving_cycle_position_percent)

    # Step 8: Cycle time confidence — decreases when cycle exceeds historical norms
    if days_since_bottom <= HISTORICAL_AVERAGE_BULL_DAYS:
        progress_ratio = days_since_bottom / HISTORICAL_AVERAGE_BULL_DAYS
        cycle_time_confidence = 100.0 - (progress_ratio * 15)
    else:
        overshoot = days_since_bottom - HISTORICAL_AVERAGE_BULL_DAYS
        cycle_time_confidence = 85.0 - min(85.0, overshoot / 10.0)
    cycle_time_confidence = _clamp_pct(cycle_time_confidence)

    return {
        "cycle_position_percent": round(cycle_position_percent, 2),
        "days_since_cycle_bottom": days_since_bottom,
        "days_since_cycle_top": days_since_top,
        "days_to_next_cycle_top": days_to_next_top,
        "days_to_next_cycle_bottom": days_to_next_bottom,
        "expected_cycle_top_date": expected_top_date.isoformat(),
        "expected_cycle_bottom_date": expected_bottom_date.isoformat(),
        "halving_cycle_position_percent": round(halving_cycle_position_percent, 2),
        "cycle_time_confidence": round(cycle_time_confidence, 2),
        "current_cycle_anchor": {
            "bottom_date": CURRENT_CYCLE_BOTTOM.isoformat(),
            "last_halving": LAST_HALVING.isoformat(),
        },
        "historical_average_cycle_length_days": HISTORICAL_AVERAGE_CYCLE_DAYS,
        "historical_average_bull_length_days": HISTORICAL_AVERAGE_BULL_DAYS,
        "historical_average_bear_length_days": HISTORICAL_AVERAGE_BEAR_DAYS,
    }
