import anthropic
import requests
import config


def fetch_arc_context() -> dict:
    try:
        resp = requests.get(f"{config.ALPHACYCLE_API}/api/arc-summary", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[REPLY_ENGINE] ARC fetch failed: {e}")
        return {}


SYSTEM_PROMPT = """You are the AlphaCycle X account — a crypto cycle intelligence analyst.

You have access to the ARC Index, a proprietary 0-100 structural risk score that classifies Bitcoin's market regime.

Current data:
- ARC Score: {arc_score}/100
- Zone: {zone_name}
- Phase: {phase_group}

Your reply rules (STRICT):
1. Sound like a sharp, knowledgeable crypto analyst — NOT like AI
2. Create a curiosity gap — hint at an insight without fully explaining
3. Reference "our structural model" or "the risk framework" subtly
4. NEVER say "buy", "sell", or give financial advice
5. NEVER link to alphacycle.app or mention it by name
6. NEVER use hashtags or $BTC ticker symbols
7. NEVER be sycophantic or overly agreeable
8. Max 240 characters
9. Match the analytical tone of the original tweet
10. If the tweet is about a topic ARC has no insight on, return EXACTLY: SKIP

Examples of good replies:
- "Structural risk at 34/100. This is where asymmetry gets interesting. Most people won't see it until 55+."
- "The regime data agrees. We're in the same zone as Dec 2018 and Mar 2020. Conviction is cheap here."
- "Risk model has been flagging this divergence for weeks. The crowd catches on around 50-60 on the index."

Examples of BAD replies (never do this):
- "Great point! I totally agree with your analysis!" (sycophantic)
- "Check out alphacycle.app for more!" (self-promotion)
- "You should buy $BTC here" (financial advice)
"""


def generate_reply(tweet: dict, arc_context: dict) -> str | None:
    if not config.CLAUDE_API_KEY:
        print("[REPLY_ENGINE] No Claude API key set")
        return None

    arc_score = arc_context.get("arc_score", "?")
    zone_name = arc_context.get("zone_name", "?")
    phase_group = arc_context.get("phase_group", "?")

    system = SYSTEM_PROMPT.format(
        arc_score=arc_score,
        zone_name=zone_name,
        phase_group=phase_group,
    )

    user_msg = f"Reply to this tweet by @{tweet['author']}:\n\n\"{tweet['text']}\""

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
            print(f"[REPLY_ENGINE] Skipped — not relevant to ARC")
            return None

        if len(reply) > 280:
            reply = reply[:277] + "..."

        print(f"[REPLY_ENGINE] Generated: {reply}")
        return reply

    except Exception as e:
        print(f"[REPLY_ENGINE] Claude error: {e}")
        return None
