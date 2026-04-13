"""
arc_config.py - AlphaCycle ARC Index Canonical Formula
Single source of truth for ARC weights, zones, and version.

LOCKED - NEVER modify without explicit approval from Noah + version bump.
Any change requires: research justification + backtest validation + CHANGELOG entry.

Current version: ARC v1.1 (see ARC_FORMULA_VERSION)
Formula: ma_200w*0.35 + drawdown*0.25 + liquidity*0.25 + fear_greed*0.15
"""
from __future__ import annotations

# Version identifier - bump on ANY methodology change
ARC_FORMULA_VERSION: str = "1.1"

# Locked weights - these must match compute_arc_score() in scoring.py
# and all ARC calculations in backtest_engine.py
ARC_WEIGHTS: dict[str, float] = {
    "trend":     0.35,
    "drawdown":  0.25,
    "liquidity": 0.25,
    "sentiment": 0.15,
}

# Zone definitions - must match phaseOf() in index.html and get_zone_name() in main.py
# Format: (lo_inclusive, hi_exclusive, name, hex_color)
ARC_ZONES: list[tuple[int, int, str, str]] = [
    (0,  30, "Deep Value",   "#00DC78"),
    (30, 40, "Accumulation", "#00B4D8"),
    (40, 60, "Expansion",    "#58A6FF"),
    (60, 70, "Risk Rising",  "#FF9500"),
    (70, 101, "Euphoria",     "#FF3B3B"),
]


def get_zone(arc_display: float) -> dict:
    """Return zone dict {name, color, lo, hi} for a given display ARC score."""
    for lo, hi, name, color in ARC_ZONES:
        if lo <= arc_display < hi:
            return {"name": name, "color": color, "lo": lo, "hi": hi}
    return {"name": "Euphoria", "color": "#FF3B3B", "lo": 70, "hi": 100}


def assert_weights_sum() -> None:
    """Sanity check: weights must sum to 1.0. Call on import to catch drift."""
    total = sum(ARC_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, (
        f"ARC_WEIGHTS sum to {total:.6f}, must be exactly 1.0. "
        f"Check arc_config.py - never edit weights without approval."
    )


assert_weights_sum()
