"""
AlphaCycle content prompt builder: loads master prompts from prompts/*.txt,
injects ARC context, history, and randomized angles. No HTTP API calls here;
reads posted-topic history from SQLite via database.get_recent_topics.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import config
import database

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

REPLY_APPROACH_KEYS = (
    "agree_and_deepen",
    "reframe_with_data",
    "historical_parallel",
    "respectful_counter",
    "short_data_drop",
)

HOOK_ACTIVE_LABEL = "ACTIVE"
HOOK_INACTIVE_LABEL = "INACTIVE"

# Monday=0 .. Sunday=6; keys must match bullets in prompts/post_system.txt
POST_TYPE_BY_WEEKDAY: tuple[str, ...] = (
    "contrarian_signal",
    "structural_insight",
    "contrast",
    "cycle_pattern",
    "narrative",
    "minimal_narrative",
    "weekly_recap",
)


def _read_prompt_file(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


def _format_arc_block(arc_data: dict[str, Any] | None) -> str:
    a = arc_data or {}
    raw = a.get("arc_score", "?")
    disp = a.get("arc_display", raw)
    zone = a.get("zone_name", a.get("zone", "?"))
    phase = a.get("phase_group", a.get("phase", "?"))
    pct = a.get("percentile", a.get("arc_percentile", "?"))
    fg = a.get("fear_greed", a.get("fear_greed_index", a.get("fear_greed_value", "?")))
    lines = [
        f"ARC-style structural score (raw / display): {raw} / {disp}",
        f"Regime zone: {zone}",
        f"Phase cluster: {phase}",
        f"Percentile (if available): {pct}",
        f"Sentiment proxy — Fear and Greed (if available): {fg}",
    ]
    bp = a.get("btc_price")
    if bp is not None and bp != "" and bp != "?":
        lines.append(f"BTC price (USD, snapshot): {bp}")
    pos = a.get("position")
    if pos is not None and pos != "":
        lines.append(f"Suggested position (context): {pos}")
    alloc = a.get("allocation")
    if alloc is not None and alloc != "":
        lines.append(f"Allocation band (context): {alloc}")
    r12 = a.get("return_12m")
    if r12 is not None and r12 != "":
        lines.append(f"Zone 12M return context (historical avg %): {r12}")
    wr = a.get("win_rate")
    if wr is not None and wr != "":
        lines.append(f"Zone 12M win rate context (%): {wr}")
    dst = a.get("days_since_top")
    if dst is not None and dst != "":
        lines.append(f"Days since cycle top (model): {dst}")
    eb = a.get("est_bottom")
    if eb is not None and eb != "":
        lines.append(f"Estimated bottom / cycle timing note: {eb}")
    return "\n".join(lines)


def _format_reply_history(reply_history: Sequence[str] | None) -> str:
    hist = list(reply_history or [])[:10]
    if not hist:
        return "(none yet — vary your openers and avoid clichés.)"
    parts = []
    for i, text in enumerate(hist, 1):
        t = (text or "").strip().replace("\n", " ")
        parts.append(f"{i}. {t[:220]}")
    return "\n".join(parts)


def _format_posted_topics(posted_topics: Sequence[str] | None) -> str:
    topics = list(posted_topics or [])
    if not topics:
        return "(none recorded — still avoid repeating stale macro memes.)"
    parts = []
    for i, t in enumerate(topics[:40], 1):
        s = (t or "").strip().replace("\n", " ")
        parts.append(f"{i}. {s[:280]}")
    return "\n".join(parts)


def _join_posted_topics_lines(lines: list[str]) -> str:
    """One topic per line: summary (post_type) for post_system.txt {posted_topics}."""
    clean = [(x or "").strip() for x in lines if (x or "").strip()]
    if not clean:
        return (
            "(none in posted_topics table yet — still avoid repeating stale macro memes.)"
        )
    return "\n".join(clean[:40])


def _pick_post_type(day_of_week: int) -> str:
    """Monday=0 .. Sunday=6 (datetime.weekday())."""
    return POST_TYPE_BY_WEEKDAY[int(day_of_week) % 7]


def build_reply_prompt(
    tweet_text: str,
    tweet_author: str,
    reply_history: Sequence[str] | None,
    arc_data: dict[str, Any] | None,
) -> tuple[str, str]:
    """
    Build full system-style prompt string for a reply-generation Claude call.
    Randomly picks 1 of 5 approaches; 40% chance hook = ACTIVE (see reply_system.txt).
    Returns (system_prompt, approach_key) so callers can log the approach after post.
    """
    base = _read_prompt_file("reply_system.txt")
    logger.info("[GROWTH ENGINE] Prompts loaded successfully")
    approach_key = random.choice(REPLY_APPROACH_KEYS)
    hook_instruction = (
        HOOK_ACTIVE_LABEL
        if random.random() < float(config.REPLY_HOOK_PROBABILITY)
        else HOOK_INACTIVE_LABEL
    )
    author = tweet_author.lstrip("@")
    text = tweet_text.strip()
    history = _format_reply_history(reply_history)
    arc_block = _format_arc_block(arc_data)
    # Use replace (not str.format) so { } inside tweet_text does not break.
    for key, val in (
        ("{arc_data_block}", arc_block),
        ("{approach}", approach_key),
        ("{hook_instruction}", hook_instruction),
        ("{tweet_author}", author),
        ("{tweet_text}", text),
        ("{reply_history}", history),
    ):
        base = base.replace(key, val)
    return base, approach_key


def build_post_prompt(
    arc_data: dict[str, Any] | None,
    day_of_week: int | None = None,
) -> str:
    """
    Build full system-style prompt string for an original-post Claude call.
    day_of_week: Monday=0 .. Sunday=6; default UTC now.
    Loads recent angles from database.get_recent_topics (posted_topics table),
    one line per topic: summary (post_type).
    """
    if day_of_week is None:
        day_of_week = datetime.now(timezone.utc).weekday()
    base = _read_prompt_file("post_system.txt")
    logger.info("[GROWTH ENGINE] Prompts loaded successfully")
    post_type = _pick_post_type(int(day_of_week))
    arc_block = _format_arc_block(arc_data)
    topic_lines = database.get_recent_topics(days=int(config.TOPIC_LOOKBACK_DAYS))
    topics = _join_posted_topics_lines(topic_lines)
    for key, val in (
        ("{arc_data_block}", arc_block),
        ("{post_type}", post_type),
        ("{posted_topics}", topics),
    ):
        base = base.replace(key, val)
    return base
