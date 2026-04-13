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

import anthropic

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

# Injected as {reply_pattern} — keys must match config.REPLY_PATTERNS
REPLY_PATTERN_TEXTS: dict[str, str] = {
    "contrarian_insight_hook": """Pattern: contrarian_insight_hook
Structure your reply as a contrarian insight:
- Sentence 1: Name what everyone thinks or expects (the consensus)
- Sentence 2: Show why the structure says something different
- Sentence 3: Open loop — imply a consequence without stating it
The reader should finish your reply thinking "wait, what does that mean?"
""",
    "cycle_reframe": """Pattern: cycle_reframe
Structure your reply as a cycle reframe:
- Sentence 1: Name what everyone is watching (usually price)
- Sentence 2: Point to what they're NOT watching (liquidity, leverage, positioning)
- Optional sentence 3: What the blind spot has meant historically
Shift the conversation from price to structure.
""",
    "historical_memory": """Pattern: historical_memory
Structure your reply as a historical memory:
- Sentence 1: Reference a specific historical phase (year + what happened)
- Sentence 2: Connect subtly to today (similar conditions, not same outcome)
- NO sentence 3. Keep it short. Let the pattern speak.
Do NOT state what happened next. Let the reader wonder.
""",
    "structural_insight": """Pattern: structural_insight
Structure your reply as a structural insight:
- Sentence 1: What the crowd sees or does
- Sentence 2: What the structure underneath shows
- That's it. Two sentences. Maximum.
Brevity = authority. Say more with less.
""",
}


def _reply_pattern_catalog() -> dict[str, float]:
    raw = getattr(config, "REPLY_PATTERNS", None) or {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.strip():
            continue
        try:
            w = float(v)
        except (TypeError, ValueError):
            w = 0.1
        if w > 0:
            out[k.strip()] = w
    if not out:
        for k in REPLY_PATTERN_TEXTS:
            out[k] = 0.25
    return out


def select_pattern_key() -> str:
    cat = _reply_pattern_catalog()
    keys = list(cat.keys())
    weights = [cat[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def select_different_pattern_key(banned: str) -> str:
    cat = _reply_pattern_catalog()
    keys = [k for k in cat if k != banned]
    if not keys:
        return banned
    weights = [cat[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def _pick_pattern_avoiding_double_streak() -> str:
    """If last two reply_history patterns match, do not pick that same key again."""
    streak = database.get_last_reply_patterns(2)
    pattern_key = select_pattern_key()
    if (
        len(streak) >= 2
        and streak[0]
        and streak[0] == streak[1]
        and pattern_key == streak[0]
    ):
        pattern_key = select_different_pattern_key(streak[0])
    return pattern_key


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
    ath = a.get("btc_ath")
    if ath is not None and str(ath).strip() not in ("", "?", "0", "0.0"):
        try:
            av = float(ath)
            if av > 0:
                lines.append(f"BTC ATH (USD, AlphaCycle API snapshot): {av:,.0f}")
        except (TypeError, ValueError):
            pass
    if bp is not None and ath is not None:
        try:
            pv = float(bp)
            av = float(ath)
            if av > 0 and pv > 0:
                dd_pct = (pv - av) / av * 100.0
                lines.append(f"Drawdown from ATH (vs snapshot above): {round(dd_pct, 1)}%")
        except (TypeError, ValueError):
            pass
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


def _arc_score_float(arc_data: dict[str, Any] | None) -> float:
    """Prefer display score for banding; fallback raw combined."""
    a = arc_data or {}
    for key in ("arc_display", "arc_score", "combined_score"):
        v = a.get(key)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 50.0


def _get_market_context(arc_score: float) -> str:
    """ARC-band macro line for prompts — no hardcoded prices in static .txt files."""
    try:
        a = float(arc_score) if arc_score else 50.0
    except (TypeError, ValueError):
        a = 50.0
    if a < 30:
        return (
            "Structural risk at historic lows. "
            "Cycle positioning favors long time horizons."
        )
    if a < 40:
        return (
            "Structure resetting. Risk declining but cycle transition not yet confirmed."
        )
    if a < 60:
        return "Mid-cycle. Structure supports continuation. Risk balanced."
    if a < 70:
        return (
            "Structural risk elevating. Cycle maturity increasing. Caution warranted."
        )
    return (
        "Structural risk at historic highs. "
        "Cycle positioning favors capital preservation."
    )


def _format_factual_reference(
    arc_score: Any | None,
    btc_price: Any | None,
    ath_price: Any | None,
) -> str:
    """Single line for qa_system.txt — no hardcoded ATH/BTC in the static prompt file."""
    try:
        arv = float(arc_score) if arc_score is not None else 50.0
    except (TypeError, ValueError):
        arv = 50.0
    bp_s = "?"
    if btc_price is not None:
        try:
            bp_s = f"{float(btc_price):,.0f}"
        except (TypeError, ValueError):
            bp_s = str(btc_price).strip() or "?"
    ath_s = "?"
    if ath_price is not None:
        try:
            ath_s = f"{float(ath_price):,.0f}"
        except (TypeError, ValueError):
            ath_s = str(ath_price).strip() or "?"
    return f"FACTUAL REFERENCE: ARC={arv}, BTC=${bp_s}, ATH=${ath_s}"


def _format_reply_history(reply_history: Sequence[str] | None) -> str:
    cap = max(1, int(getattr(config, "MAX_REPLY_HISTORY", 5)))
    hist = list(reply_history or [])[:cap]
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
    *,
    pattern_key: str | None = None,
) -> tuple[str, str, str]:
    """
    Build full system-style prompt string for a reply-generation Claude call.
    Randomly picks 1 of 5 approaches and 1 structural pattern (see reply_system.txt).
    40% chance hook = ACTIVE. Returns (system_prompt, approach_key, pattern_key).
    If pattern_key is set, use that pattern (QA retry / pattern switch) instead of streak pick.
    """
    base = _read_prompt_file("reply_system.txt")
    logger.info("[GROWTH ENGINE] Prompts loaded successfully")
    approach_key = random.choice(REPLY_APPROACH_KEYS)
    cat = _reply_pattern_catalog()
    if pattern_key and pattern_key in cat:
        pattern_key_out = pattern_key
    elif pattern_key and pattern_key in REPLY_PATTERN_TEXTS:
        pattern_key_out = pattern_key
    else:
        pattern_key_out = _pick_pattern_avoiding_double_streak()
    pattern_body = REPLY_PATTERN_TEXTS.get(
        pattern_key_out,
        f"Pattern: {pattern_key_out}\nFollow a clear 2–3 sentence structure; stay under 270 characters.",
    )
    hook_instruction = (
        HOOK_ACTIVE_LABEL
        if random.random() < float(config.REPLY_HOOK_PROBABILITY)
        else HOOK_INACTIVE_LABEL
    )
    has_hook = hook_instruction == HOOK_ACTIVE_LABEL
    logger.info(
        "[GROWTH ENGINE] Reply: approach=%s, pattern=%s, hook=%s",
        approach_key,
        pattern_key_out,
        has_hook,
    )
    author = tweet_author.lstrip("@")
    text = tweet_text.strip()
    history = _format_reply_history(reply_history)
    arc_block = _format_arc_block(arc_data)
    band = _get_market_context(_arc_score_float(arc_data))
    market_ctx = f"MARKET CONTEXT: {band}"
    # Use replace (not str.format) so { } inside tweet_text does not break.
    for key, val in (
        ("{market_context}", market_ctx),
        ("{arc_data_block}", arc_block),
        ("{approach}", approach_key),
        ("{reply_pattern}", pattern_body.strip()),
        ("{hook_instruction}", hook_instruction),
        ("{tweet_author}", author),
        ("{tweet_text}", text),
        ("{reply_history}", history),
    ):
        base = base.replace(key, val)
    return base, approach_key, pattern_key_out


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
    band = _get_market_context(_arc_score_float(arc_data))
    market_ctx = f"MARKET CONTEXT: {band}"
    topic_lines = database.get_recent_topics(days=int(config.TOPIC_LOOKBACK_DAYS))
    topics = _join_posted_topics_lines(topic_lines)
    for key, val in (
        ("{market_context}", market_ctx),
        ("{arc_data_block}", arc_block),
        ("{post_type}", post_type),
        ("{posted_topics}", topics),
    ):
        base = base.replace(key, val)
    return base


def qa_check_reply(
    tweet_text: str,
    tweet_author: str,
    reply_text: str,
    *,
    arc_score: Any | None = None,
    btc_price: Any | None = None,
    ath_price: Any | None = None,
) -> tuple[bool, str | None]:
    """
    Second Claude call (Haiku): PASS or FAIL: reason.
    Returns (True, None) on PASS, (False, reason) on FAIL or API error.
    arc_score / btc_price / ath_price: injected into qa_system.txt as {factual_reference}.
    """
    if not getattr(config, "CLAUDE_API_KEY", None):
        logger.warning("[QA] No CLAUDE_API_KEY")
        return False, "no_api_key"

    try:
        template = _read_prompt_file("qa_system.txt")
    except FileNotFoundError as e:
        logger.error("[QA] %s", e)
        return False, "missing_qa_prompt"

    author = (tweet_author or "").strip().lstrip("@")
    t = (tweet_text or "").strip()
    r = (reply_text or "").strip()
    fact = _format_factual_reference(arc_score, btc_price, ath_price)
    for key, val in (
        ("{factual_reference}", fact),
        ("{tweet_text}", t),
        ("{tweet_author}", author),
        ("{reply_text}", r),
    ):
        template = template.replace(key, val)

    model = (getattr(config, "QA_MODEL", None) or "claude-haiku-4-5-20251001").strip()
    try:
        client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
        response = client.messages.create(
            model=model,
            max_tokens=50,
            messages=[{"role": "user", "content": template}],
        )
    except Exception as e:
        logger.warning("[QA] Claude QA call failed: %s", e)
        return False, f"qa_api_error:{str(e)[:180]}"

    try:
        raw = (response.content[0].text or "").strip()
    except (IndexError, AttributeError):
        return False, "empty_qa_response"

    first_line = raw.split("\n", 1)[0].strip()
    upper = first_line.upper()
    if upper == "PASS" or upper.startswith("PASS "):
        return True, None
    if upper.startswith("FAIL"):
        reason = first_line[4:].lstrip(": ").strip() or raw[:300]
        return False, reason
    if "FAIL" in upper:
        return False, first_line[:300]
    return False, first_line[:300] if first_line else raw[:300]


_QA_PLACEHOLDER_REPLY = (
    "[Could not generate reply text after retries — post manually.]"
)


def _build_qa_replacement_guide(failures: list[str]) -> str:
    """Append-once blocks keyed by failure patterns (Haiku FAIL reasons)."""
    blob = " ".join(failures).lower()
    parts: list[str] = []
    seen: set[str] = set()

    def add(key: str, text: str) -> None:
        if key not in seen:
            seen.add(key)
            parts.append(text)

    if "banned_word" in blob or "zone_label" in blob:
        add(
            "zone_banned",
            "\nDo NOT use ARC zone names as labels."
            "\nInstead of 'deep value territory' write 'historic structural lows'"
            "\nInstead of 'deep value zone' write 'single-digit percentile readings'"
            "\nInstead of 'accumulation phase' write 'structural positioning'"
            "\nInstead of 'accumulation zone' write 'low-risk structural environment'"
            "\nNever use zone names directly. Describe what they mean.",
        )
    if "contains_prediction" in blob or "prediction" in blob:
        add(
            "pred",
            "\nDo NOT predict what happens next."
            "\nReplace any 'will', 'next', 'coming' + outcome with an observation."
            "\nDescribe what IS, not what WILL BE.",
        )
    if "ai_sound" in blob:
        add(
            "ai",
            "\nYour reply sounded like AI. Rewrite completely."
            "\nUse shorter words. Be direct. Sound like a sharp trader at a bar.",
        )
    if "topic_hijack" in blob:
        add(
            "hijack",
            "\nYour opening ignored the author's topic. First sentence must"
            "\nengage THEIR subject (oil, tariffs, Fed, etc.). Earn crypto"
            "\nlater in the reply if at all — never open with Bitcoin/stablecoins"
            "\nwhen they did not.",
        )
    if "recycled_data" in blob:
        add(
            "recycled",
            "\nDo not stack boilerplate metrics (drawdown %, stablecoins,"
            "\npercentiles, leverage flushed, structural risk lows, smart money)."
            "\nPick ONE angle tied to the tweet, or zero numbers.",
        )
    if "generic_opener" in blob:
        add(
            "generic",
            "\nYour first sentence was generic. Start by referencing"
            "\na SPECIFIC claim or data point from the original tweet.",
        )
    if "over_260" in blob:
        add(
            "len",
            "\nYour reply was too long. Maximum 260 characters."
            "\nCut to 2 sentences maximum.",
        )
    if "factual" in blob:
        add(
            "fact",
            "\nYour reply had a factual error. Compare claims to the snapshot"
            "\nand to well-known event timing before writing.",
        )
    if "logic" in blob:
        add(
            "logic",
            "\nYour reply had a logic error. Read the tweet again carefully."
            "\nMake sure your commentary matches what the author actually said.",
        )
    if "brand" in blob:
        add(
            "brand",
            "\nNever mention AlphaCycle, ARC, our dashboard, or our model."
            "\nUse 'structural risk composite' or 'risk percentile readings' instead.",
        )
    if "sales" in blob:
        add(
            "sales",
            "\nRemove any sales language. You observe, you don't sell.",
        )
    if "no_insight" in blob:
        add(
            "no_insight",
            "\nYour reply just restated the tweet. Add something NEW."
            "\nWhat dimension did the author miss? Liquidity? Leverage?"
            "\nHistorical parallel? Structural context? Add ONE.",
        )
    if "too_generic" in blob:
        add(
            "too_generic",
            "\nYour reply was too generic. Any account could write this."
            "\nMake it specific: use a number, a timeframe, a structural"
            "\nobservation that only someone tracking cycle risk would know.",
        )
    if "no_structural_lens" in blob:
        add(
            "no_structural_lens",
            "\nYour reply had no structural cycle lens."
            "\nConnect it to: liquidity direction, leverage levels,"
            "\nsentiment vs structure divergence, or cycle positioning."
            "\nIf the tweet is about price, reframe to structure.",
        )
    if "low_authority" in blob:
        add(
            "low_authority",
            "\nYour reply sounded like retail commentary."
            "\nWrite like a macro strategist. Precise. Measured."
            "\nNo slang. No hype. No casual language.",
        )
    return "".join(parts)


def generate_reply_with_qa(
    tweet: dict,
    arc_data: dict | None = None,
) -> tuple[str, str, int, str | None, str | None]:
    """
    Sonnet reply + Haiku QA loop (up to QA_MAX_ATTEMPTS).
    Always returns a non-empty reply_text (placeholder if needed).
    Returns: reply_text, qa_status, attempts, approach_key, pattern_key
    qa_status: \"PASS\" or \"FAIL_3x:reasons\"
    """
    import reply_engine

    author_log = (tweet.get("author") or "").strip().lstrip("@") or "unknown"
    max_a = max(1, int(getattr(config, "QA_MAX_ATTEMPTS", 3)))

    if not getattr(config, "QA_ENABLED", True):
        rt, ak, pk = reply_engine.generate_reply(tweet, arc_data=arc_data)
        if not rt:
            rt = _QA_PLACEHOLDER_REPLY
        return rt, "PASS", 1, ak, pk

    failures: list[str] = []
    last_reply = ""
    last_ak: str | None = None
    last_pk: str | None = None

    for attempt in range(1, max_a + 1):
        extra = ""
        force_pattern: str | None = None
        if attempt > 1:
            extra = (
                "Write something completely different from your last attempt."
            )
            if last_pk:
                force_pattern = select_different_pattern_key(last_pk)
            else:
                force_pattern = select_pattern_key()
        rt, ak, pk = reply_engine.generate_reply(
            tweet,
            extra_instruction=extra,
            arc_data=arc_data,
            pattern_key=force_pattern,
        )
        if rt:
            last_reply = rt
            last_ak = ak
            last_pk = pk
        else:
            failures.append("empty_reply")
            logger.info(
                "[QA] @%s: empty generation (attempt %s)",
                author_log,
                attempt,
            )
            continue

        ad = arc_data or {}
        passed, reason = qa_check_reply(
            tweet.get("text") or "",
            tweet.get("author") or "",
            rt,
            arc_score=ad.get("arc_display", ad.get("arc_score")),
            btc_price=ad.get("btc_price"),
            ath_price=ad.get("btc_ath"),
        )
        if passed:
            logger.info("[QA] @%s: PASS (attempt %s)", author_log, attempt)
            return rt, "PASS", attempt, ak, pk

        fail_reason = reason or "unknown"
        failures.append(fail_reason)
        logger.info(
            "[QA] @%s: FAIL - %s (attempt %s)",
            author_log,
            fail_reason,
            attempt,
        )

    summary = "; ".join(failures) if failures else "unknown"
    logger.warning(
        "[QA] @%s: %sx FAIL - sending anyway with warning",
        author_log,
        max_a,
    )
    out = last_reply or _QA_PLACEHOLDER_REPLY
    return out, f"FAIL_3x:{summary}", max_a, last_ak, last_pk
