"""
alerts.py — AlphaCycle regime-change alert engine.

On every data refresh, compare the live ARC zone against the last zone we alerted
on (persisted in the `alert_log` Supabase table). When the zone changes, post a
message to a Telegram channel and log the event so we never double-fire.

Design notes:
- Fully self-contained and defensive: every public function swallows its own
  errors and returns a status flag. It must NEVER raise into the refresh loop.
- Telegram is sent via stdlib urllib (no extra dependency).
- First run with an empty alert_log initialises a silent baseline (no message),
  so a fresh deploy does not spam a "change" on the very first tick.
- Email alerts are intentionally NOT wired here yet (planned via email_captures /
  Beehiiv). Hook point marked below.

Required ENV (set in Railway — never hardcode):
  TELEGRAM_BOT_TOKEN         the bot's API token (same bot may already exist)
  TELEGRAM_ALERT_CHANNEL_ID  target channel/chat id, e.g. "@alphacycle_alerts"
                             or a numeric id like "-1001234567890"
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request

logger = logging.getLogger("alphacycle.alerts")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALERT_CHANNEL_ID = os.environ.get("TELEGRAM_ALERT_CHANNEL_ID", "")

# Zone order from least risk (opportunity) to most risk. Index used to decide
# whether a transition is "up" (toward risk) or "down" (toward opportunity).
ZONE_ORDER = ["Deep Value", "Accumulation", "Expansion", "Risk Rising", "Euphoria"]


def _zone_for(arc_score: float) -> str:
    """Classify a RAW ARC score into a regime zone name (matches arc_config.ARC_ZONES)."""
    try:
        from arc_config import get_zone
    except ImportError:
        from backend.arc_config import get_zone
    return get_zone(float(arc_score))["name"]


def _supabase():
    try:
        from database import supabase
    except ImportError:
        try:
            from backend.database import supabase
        except Exception:
            return None
    return supabase


def _last_alerted_zone():
    """Return the zone_to of the most recent alert_log row, or None if table empty/unavailable."""
    sb = _supabase()
    if not sb:
        return None
    try:
        res = (
            sb.table("alert_log")
            .select("zone_to")
            .order("triggered_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0].get("zone_to")
    except Exception as e:
        logger.warning("alert_log read failed: %s", e)
    return None


def _log_alert(arc_score: float, zone_from, zone_to: str, emails_sent: int = 0) -> None:
    sb = _supabase()
    if not sb:
        return
    try:
        sb.table("alert_log").insert(
            {
                "arc_score": int(round(float(arc_score))),
                "zone_from": zone_from,
                "zone_to": zone_to,
                "emails_sent": emails_sent,
            }
        ).execute()
    except Exception as e:
        logger.warning("alert_log insert failed: %s", e)


def _format_message(zone_from: str, zone_to: str, arc_score: float, btc_price) -> str:
    try:
        up = ZONE_ORDER.index(zone_to) > ZONE_ORDER.index(zone_from)
    except ValueError:
        up = True
    head = "🔺 RISK RISING" if up else "🟢 OPPORTUNITY"
    price = ""
    try:
        if btc_price:
            price = f"\nBTC: ${float(btc_price):,.0f}"
    except Exception:
        pass
    return (
        f"⚠️ ARC REGIME CHANGE — {head}\n\n"
        f"{zone_from} → {zone_to}\n"
        f"ARC Index: {float(arc_score):.1f}{price}\n\n"
        f"The market just shifted regime. Structure before emotion.\n"
        f"— AlphaCycle · alphacycle.app/app"
    )


def send_telegram(text: str) -> bool:
    """Post a plain message to the configured Telegram alert channel. Returns success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ALERT_CHANNEL_ID:
        logger.info("Telegram alert skipped (TELEGRAM_BOT_TOKEN / TELEGRAM_ALERT_CHANNEL_ID not set)")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = json.dumps(
            {"chat_id": TELEGRAM_ALERT_CHANNEL_ID, "text": text[:4096], "disable_web_page_preview": True}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ok = json.loads(r.read().decode("utf-8")).get("ok", False)
            if not ok:
                logger.warning("Telegram sendMessage returned ok=false")
            return bool(ok)
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return False


def check_and_fire_alerts(arc_score: float, btc_price=None) -> dict:
    """
    Compare the live ARC zone with the last alerted zone. If changed, send a
    Telegram alert and log it. Safe to call on every refresh — never raises.

    Returns a small status dict for logging/debugging.
    """
    try:
        if arc_score is None:
            return {"status": "skip", "reason": "no arc_score"}
        zone_now = _zone_for(arc_score)
        zone_last = _last_alerted_zone()

        # Cold start: no history yet → set a silent baseline, do not alert.
        if zone_last is None:
            _log_alert(arc_score, None, zone_now, emails_sent=0)
            return {"status": "baseline", "zone": zone_now}

        if zone_now == zone_last:
            return {"status": "unchanged", "zone": zone_now}

        # Regime changed → alert.
        msg = _format_message(zone_last, zone_now, arc_score, btc_price)
        sent = send_telegram(msg)
        _log_alert(arc_score, zone_last, zone_now, emails_sent=0)
        # TODO(email): when ready, fan out to email_captures / Beehiiv subscribers here.
        logger.info("ARC regime change: %s -> %s (telegram_sent=%s)", zone_last, zone_now, sent)
        return {"status": "fired", "from": zone_last, "to": zone_now, "telegram_sent": sent}
    except Exception as e:
        logger.warning("check_and_fire_alerts error (non-fatal): %s", e)
        return {"status": "error", "error": str(e)}
