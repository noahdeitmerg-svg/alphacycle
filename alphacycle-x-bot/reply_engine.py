import anthropic
import config
import daily_post_engine
import database
from growth_engine import build_reply_prompt


def generate_reply(
    tweet: dict,
    extra_instruction: str = "",
    arc_data: dict | None = None,
    pattern_key: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """
    Build prompt via growth_engine + live ARC from daily_post_engine; call Claude.
    Returns (reply_text, approach_key, pattern_key) for pending row / reply_history.
    optional arc_data: skip refetch when provided (e.g. QA loop).
    extra_instruction: appended to the user message (short retry hint only; no QA dump).
    pattern_key: if set, forces that structural pattern in build_reply_prompt (QA retry).
    """
    if not config.CLAUDE_API_KEY:
        print("[REPLY_ENGINE] No Claude API key set")
        return None, None, None

    if arc_data is None:
        arc_data = daily_post_engine.fetch_arc_data() or {}
    history = database.get_reply_history_texts_for_prompt(config.MAX_REPLY_HISTORY)

    try:
        system, approach_key, pattern_key = build_reply_prompt(
            tweet.get("text") or "",
            tweet.get("author") or "",
            history,
            arc_data,
            pattern_key=pattern_key,
        )
    except Exception as e:
        print(f"[REPLY_ENGINE] build_reply_prompt failed: {e}")
        return None, None, None

    # Relevance/SKIP gate removed: scanner + Telegram approval are the filters; no second "not_relevant" drop here.
    user_msg = (
        "Write the reply only. Follow the system instructions. "
        "Do not output SKIP or any placeholder — always produce reply text for this tweet. "
        "No preamble."
    )
    if (extra_instruction or "").strip():
        user_msg = user_msg + "\n\n" + (extra_instruction or "").strip()

    try:
        client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )

        reply = response.content[0].text.strip()

        if not reply:
            return None, None, None
        # Never queue the literal placeholder word as a reply (not the old "relevance" filter).
        if reply.upper() == "SKIP":
            return None, None, None

        if len(reply) > 270:
            reply = reply[:270]

        print(f"[REPLY_ENGINE] Generated: {reply}")
        return reply, approach_key, pattern_key

    except Exception as e:
        print(f"[REPLY_ENGINE] Claude error: {e}")
        return None, None, None
