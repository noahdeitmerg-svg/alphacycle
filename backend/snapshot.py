"""
AlphaCycle Snapshot Generator
Aggregates all relevant data for content generation (X/Twitter posts).
"""
from datetime import datetime, timezone
from typing import Optional


def generate_post_templates(snapshot: dict) -> dict:
    """
    Generates ready-to-use post texts based on the current market snapshot.
    Returns multiple template types.
    """
    arc = snapshot.get("arc_score", 50)
    phase = snapshot.get("phase_label", "Moderate Risk")
    btc = snapshot.get("btc_price", 0)
    fg = snapshot.get("fear_greed", 50)
    position = snapshot.get("position", "HOLD")
    upside = snapshot.get("upside_pct", 0)
    downside = snapshot.get("downside_pct", 0)
    days_bottom = snapshot.get("days_since_bottom", 0)
    cycle_phase = snapshot.get("cycle_phase_label", "Mid Bull")
    signal_type = snapshot.get("signal_type", "NONE")
    allocation = snapshot.get("allocation", "60-80%")
    ma_dev = snapshot.get("ma_200w_dev", 0)
    drawdown = snapshot.get("drawdown_pct", 0)
    st_score = snapshot.get("st_score", 50)

    # Formatting
    btc_fmt = f"${btc:,.0f}" if btc else "N/A"
    date_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
    arc_int = int(round(arc))
    fg_int = int(round(fg))
    up_int = int(round(upside))
    dn_int = int(round(downside))

    # Phase Emoji
    phase_emoji = {
        "Early Bull": "\U0001f7e2",
        "Mid Bull": "\U0001f535",
        "Late Bull": "\U0001f7e1",
        "Distribution": "\U0001f7e0",
        "Bear / Risk Off": "\U0001f534",
        "Late Bear": "\U0001f7e3",
        "Transition": "\u26aa",
    }.get(cycle_phase, "\U0001f535")

    # Signal Emoji
    signal_emoji = {
        "BOTTOM_CONFIRMED": "\U0001f6a8",
        "BOTTOM_WARNING": "\u26a0\ufe0f",
        "BOTTOM_WATCH": "\U0001f440",
        "TOP_CONFIRMED": "\U0001f6a8",
        "TOP_WARNING": "\u26a0\ufe0f",
        "TOP_WATCH": "\U0001f440",
        "NONE": "",
    }.get(signal_type, "")

    # Template 1: Daily ARC Update
    t1 = f"""ARC Index Update - {date_str}

ARC Score: {arc_int}/100
Phase: {phase}
BTC: {btc_fmt}

{phase_emoji} Cycle Phase: {cycle_phase}
ST Score: {st_score}/100
Fear & Greed: {fg_int}

Signal: {position}
Allocation: {allocation}

30-90d Outlook:
Upside: +{up_int}%
Downside: -{dn_int}%

{days_bottom} days since cycle bottom.

Not financial advice. DYOR.
alphacycle.app"""

    # Template 2: Signal Alert (only when active signal)
    if signal_type != "NONE":
        t2 = f"""{signal_emoji} AlphaCycle Signal Alert

{signal_type.replace('_', ' ')}

ARC Index: {arc_int}/100
BTC: {btc_fmt}
Fear & Greed: {fg_int}

What this means:
{_signal_description(signal_type, arc_int, cycle_phase)}

Not financial advice. DYOR.
alphacycle.app"""
    else:
        t2 = None

    # Template 3: Educational / Context
    drawdown_pct_val = int(round(drawdown * 100)) if drawdown else "N/A"
    t3 = f"""Where are we in the Bitcoin cycle?

{phase_emoji} {cycle_phase} - Day {days_bottom}

ARC Index: {arc_int}/100
Structural risk level: {phase}

Key inputs:
- 200W MA Dev: {int(round(ma_dev)) if ma_dev else 'N/A'}
- Drawdown from ATH: {drawdown_pct_val}%
- Fear & Greed: {fg_int}

Decision Engine says: {position}

This is not a price prediction.
It is a risk model.

alphacycle.app"""

    # Template 4: Compact / Thread Starter
    t4 = f"""Bitcoin ARC Index: {arc_int}/100 {phase_emoji}

Phase: {cycle_phase}
Signal: {position}
BTC: {btc_fmt}

Full breakdown
alphacycle.app"""

    return {
        "daily_update": t1,
        "signal_alert": t2,
        "educational": t3,
        "compact": t4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "arc_score": arc_int,
        "phase": phase,
        "signal_type": signal_type,
    }


def _signal_description(signal_type: str, arc: int, cycle_phase: str) -> str:
    """Helper for signal descriptions."""
    descriptions = {
        "BOTTOM_CONFIRMED": (
            f"Structural indicators align for a cycle bottom zone. "
            f"ARC at {arc} - historically strong accumulation territory. "
            f"Risk/reward favorable for long-term positions."
        ),
        "BOTTOM_WARNING": (
            f"Multiple bottom indicators active. "
            f"ARC at {arc} suggests elevated probability "
            f"of cycle low forming. Early accumulation zone."
        ),
        "BOTTOM_WATCH": (
            f"ARC entering low-risk territory at {arc}. "
            f"Monitor for additional confirmation signals."
        ),
        "TOP_CONFIRMED": (
            f"Distribution signals active. ARC at {arc} - "
            f"historically elevated risk zone. "
            f"Consider reducing exposure."
        ),
        "TOP_WARNING": (
            f"Multiple top indicators active. ARC at {arc}. "
            f"Risk management recommended."
        ),
        "TOP_WATCH": (
            f"ARC entering elevated zone at {arc}. "
            f"Increased caution warranted."
        ),
    }
    return descriptions.get(
        signal_type,
        f"ARC at {arc} - monitor for further signals.",
    )


def build_snapshot(
    arc_score: float,
    btc_price: float,
    eth_price: float,
    fear_greed: float,
    phase_label: str,
    position: str,
    allocation: str,
    upside_pct: float,
    downside_pct: float,
    st_score: float,
    cycle_phase_label: str,
    signal_type: str,
    days_since_bottom: int,
    btc_score: float,
    eth_score: float,
    mac_score: float,
    ma_200w_dev: Optional[float],
    drawdown_pct: Optional[float],
    expected_range: Optional[str],
    confidence: Optional[str],
) -> dict:
    """
    Builds the full snapshot dict and generates post templates.
    """
    snapshot = {
        "arc_score": round(arc_score, 1),
        "btc_price": btc_price,
        "eth_price": eth_price,
        "fear_greed": fear_greed,
        "phase_label": phase_label,
        "position": position,
        "allocation": allocation,
        "upside_pct": upside_pct,
        "downside_pct": downside_pct,
        "st_score": st_score,
        "cycle_phase_label": cycle_phase_label,
        "signal_type": signal_type,
        "days_since_bottom": days_since_bottom,
        "btc_score": round(btc_score, 1),
        "eth_score": round(eth_score, 1),
        "mac_score": round(mac_score, 1),
        "ma_200w_dev": ma_200w_dev,
        "drawdown_pct": drawdown_pct,
        "expected_range": expected_range,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    snapshot["post_templates"] = generate_post_templates(snapshot)

    return snapshot
