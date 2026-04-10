"""
AlphaCycle content prompt builder: loads master prompts from prompts/*.txt,
injects ARC context, history, and randomized angles. No API calls here.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

REPLY_APPROACH_KEYS = (
    "agree_and_deepen",
    "reframe_with_data",
    "historical_parallel",
    "respectful_counter",
    "short_data_drop",
)

REPLY_APPROACH_INSTRUCTIONS: dict[str, str] = {
    "agree_and_deepen": (
        "Angle A — agree_and_deepen: Acknowledge one specific point in their tweet, "
        "then add one layer from the structural / regime lens. Stay concise."
    ),
    "reframe_with_data": (
        "Angle B — reframe_with_data: Take their claim and reframe it using "
        "liquidity, regime, or cycle structure — without sounding argumentative."
    ),
    "historical_parallel": (
        "Angle C — historical_parallel: One tight parallel to a prior cycle phase "
        "(no dates spam); focus on structure, not nostalgia."
    ),
    "respectful_counter": (
        "Angle D — respectful_counter: Offer a measured counter-angle tied to risk "
        "regime — no personal attack, no thread-war tone."
    ),
    "short_data_drop": (
        "Angle E — short_data_drop: One crisp regime fact from the data block, "
        "connected to their tweet in a single logical hop."
    ),
}

CURIOSITY_HOOK_YES = (
    "Include a light curiosity hook: one short phrase that implies there is more "
    "to the framework without explaining it (no clickbait, no questions to the reader)."
)

CURIOSITY_HOOK_NO = (
    "Do not add a separate curiosity hook; keep a single cohesive, self-contained reply."
)

POST_TYPE_SPECS: dict[str, str] = {
    "contrarian_signal": (
        "contrarian_signal: One contrarian structural take vs crowd narrative. "
        "4-8 lines, end with share lines, not a question."
    ),
    "narrative": (
        "narrative: Tight story arc about regime shift or mispriced risk. "
        "4-8 lines, share lines at the end."
    ),
    "structural_insight": (
        "structural_insight: One clear framework insight (liquidity / cycle / risk). "
        "4-8 lines, share lines at the end."
    ),
    "contrast": (
        "contrast: Juxtapose two popular beliefs; resolve with structure not hype. "
        "4-8 lines, share lines at the end."
    ),
    "educational_thread": (
        "educational_thread: Micro-thread in one post (numbered lines allowed 1-4). "
        "Teach one idea; 4-8 lines; share lines at the end."
    ),
    "chart_post": (
        "chart_post: Describe what a chart would show conceptually (no image generation). "
        "4-8 lines; focus on axes of regime; share lines at the end."
    ),
    "minimal_narrative": (
        "minimal_narrative: Shorter tone day — still 4-8 lines but tighter; "
        "one idea; share lines at the end."
    ),
    "weekly_recap": (
        "weekly_recap: Summarize the week in regime terms (no price calls). "
        "4-8 lines; share lines at the end."
    ),
}


def _read_prompt_file(name: str) -> str:
    path = _PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


def _format_arc_block(arc_data: dict[str, Any] | None) -> str:
    a = arc_data or {}
    raw = a.get("arc_score", "?")
    disp = a.get("arc_display", raw)
    zone = a.get("zone_name", "?")
    phase = a.get("phase_group", "?")
    pct = a.get("percentile", a.get("arc_percentile", "?"))
    fg = a.get("fear_greed", a.get("fear_greed_index", a.get("fear_greed_value", "?")))
    lines = [
        f"Structural score (raw / display): {raw} / {disp}",
        f"Zone: {zone}",
        f"Phase cluster: {phase}",
        f"Percentile (if available): {pct}",
        f"Fear and Greed (if available): {fg}",
    ]
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


def _pick_post_type(day_of_week: int) -> str:
    """
    day_of_week: Monday=0 .. Sunday=6 (datetime.weekday()).
    MO / DI / MI / DO / FR / SA / SO mapping per spec.
    """
    if day_of_week == 0:  # Monday
        return random.choice(["contrarian_signal", "narrative"])
    if day_of_week == 1:  # Tuesday
        return "structural_insight"
    if day_of_week == 2:  # Wednesday
        return random.choice(["contrast", "educational_thread"])
    if day_of_week == 3:  # Thursday
        return "chart_post"
    if day_of_week == 4:  # Friday
        return random.choice(["contrast", "narrative"])
    if day_of_week == 5:  # Saturday
        return "minimal_narrative"
    return "weekly_recap"  # Sunday


def build_reply_prompt(
    tweet_text: str,
    tweet_author: str,
    reply_history: Sequence[str] | None,
    arc_data: dict[str, Any] | None,
) -> str:
    """
    Build full system-style prompt string for a reply-generation Claude call.
    Randomly picks 1 of 5 approaches; 40% chance to request a curiosity hook.
    """
    base = _read_prompt_file("reply_system.txt")
    approach_key = random.choice(REPLY_APPROACH_KEYS)
    approach_instruction = REPLY_APPROACH_INSTRUCTIONS[approach_key]
    curiosity_instruction = (
        CURIOSITY_HOOK_YES if random.random() < 0.4 else CURIOSITY_HOOK_NO
    )
    tweet_context = (
        f"Author: @{tweet_author.lstrip('@')}\n"
        f"Tweet text:\n{tweet_text.strip()}"
    )
    return (
        base.replace("{{ARC_CONTEXT}}", _format_arc_block(arc_data))
        .replace("{{REPLY_HISTORY}}", _format_reply_history(reply_history))
        .replace("{{APPROACH_INSTRUCTION}}", approach_instruction)
        .replace("{{CURIOSITY_INSTRUCTION}}", curiosity_instruction)
        .replace("{{TWEET_CONTEXT}}", tweet_context)
    )


def build_post_prompt(
    arc_data: dict[str, Any] | None,
    posted_topics: Sequence[str] | None,
    day_of_week: int | None = None,
) -> str:
    """
    Build full system-style prompt string for an original-post Claude call.
    day_of_week: Monday=0 .. Sunday=6; default UTC now.
    """
    if day_of_week is None:
        day_of_week = datetime.now(timezone.utc).weekday()
    base = _read_prompt_file("post_system.txt")
    post_key = _pick_post_type(int(day_of_week) % 7)
    post_instruction = POST_TYPE_SPECS[post_key]
    type_header = f"Selected type key: {post_key}\n{post_instruction}"
    return (
        base.replace("{{ARC_CONTEXT}}", _format_arc_block(arc_data))
        .replace("{{POSTED_TOPICS}}", _format_posted_topics(posted_topics))
        .replace("{{POST_TYPE_INSTRUCTION}}", type_header)
    )
