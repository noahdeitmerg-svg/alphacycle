import anthropic
import requests
import config
import database
import growth_engine


def fetch_arc_context() -> dict:
    try:
        resp = requests.get(f"{config.ALPHACYCLE_API}/api/arc-summary", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[REPLY_ENGINE] ARC fetch failed: {e}")
        return {}


def generate_reply(tweet: dict, arc_context: dict) -> str | None:
    if not config.CLAUDE_API_KEY:
        print("[REPLY_ENGINE] No Claude API key set")
        return None

    try:
        history = database.get_recent_reply_texts(10)
        system = growth_engine.build_reply_prompt(
            tweet.get("text") or "",
            tweet.get("author") or "",
            history,
            arc_context,
        )
    except Exception as e:
        print(f"[REPLY_ENGINE] growth_engine.build_reply_prompt failed: {e}")
        return None

    user_msg = (
        "Produce only the reply text for the TARGET TWEET in your system instructions "
        "(or exactly SKIP if instructed). No preamble."
    )

    try:
        client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )

        reply = response.content[0].text.strip()

        if reply == "SKIP":
            print("[REPLY_ENGINE] Skipped — not relevant to ARC")
            return None

        if len(reply) > 280:
            reply = reply[:277] + "..."

        print(f"[REPLY_ENGINE] Generated: {reply}")
        return reply

    except Exception as e:
        print(f"[REPLY_ENGINE] Claude error: {e}")
        return None
