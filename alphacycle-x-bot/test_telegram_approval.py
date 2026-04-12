"""
Send one test message to Telegram with POST/SKIP buttons (same as production).

SAFE TEST: In Telegram only tap SKIP.
POST triggers Telegram copy instructions only (no X API); fake tweet_id is still confusing for logs.

Usage (on server, same folder as .env):
  python3 test_telegram_approval.py
"""
import database
import telegram_bot

# Placeholder id — not a real X tweet (POST would error).
TEST_TWEET_ID = "9999999999999999999"


def main() -> None:
    database.init_db()
    database.delete_pending_reply(TEST_TWEET_ID)
    url = f"https://x.com/AlphaCycleTest/status/{TEST_TWEET_ID}"
    body = (
        "Test-Reply — nur SKIP druecken zum Pruefen. "
        "POST sendet nur Telegram (kein X), aber Tweet-ID ist Test-Daten."
    )
    if not database.insert_pending_reply(
        TEST_TWEET_ID, url, "AlphaCycleTest", body
    ):
        print("[WARN] Konnte pending nicht anlegen — evtl. schon vorhanden.")
    ok = telegram_bot.send_approval(url, body, TEST_TWEET_ID, "AlphaCycleTest")
    if ok:
        print("[OK] Telegram-Nachricht gesendet.")
        print("[OK] Oeffne Telegram: tippe SKIP (listener muss laufen: telegram_listener.py).")
        print("[!!] POST nur zum Testen des Telegram-Handoffs (optional).")
    else:
        print("[FEHLER] send_approval fehlgeschlagen — TELEGRAM_* in .env pruefen.")


if __name__ == "__main__":
    main()
