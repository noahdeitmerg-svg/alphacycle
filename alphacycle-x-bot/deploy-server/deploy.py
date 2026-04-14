"""
GitHub push webhook: verify signature, git pull, restart screen sessions via restart-screens.sh.
Runs on VPS (e.g. port 9000). No pm2; Telegram notify inline only.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import subprocess
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

logger = logging.getLogger("deploy_server")

REPO_PATH = os.getenv("BOT_REPO_PATH", "/root/alphacycle-repo/alphacycle-x-bot")


def _github_webhook_secret() -> str:
    """
    Strip whitespace and CR/LF from env (common when deploy-server.env was
    edited on Windows or has trailing spaces). GitHub signs with the exact
    secret configured in the webhook UI; VPS value must match those bytes.
    """
    return (os.getenv("GITHUB_WEBHOOK_SECRET") or "").strip()


def _merge_telegram_from_bot_env() -> None:
    """
    Read TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from BOT_REPO_PATH/.env
    when set there (same file as bot.py). Values override empty or
    placeholder shell env so deploy-server.env can omit Telegram lines.
    """
    p = Path(REPO_PATH) / ".env"
    if not p.is_file():
        return
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    vals = dotenv_values(p)
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        raw = (vals.get(key) or "").strip()
        if not raw:
            continue
        cur = (os.environ.get(key) or "").strip().strip('"').lower()
        placeholders = {"", "optional", "optional-gleicher-bot"}
        if cur in placeholders or not os.environ.get(key):
            os.environ[key] = raw


_merge_telegram_from_bot_env()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception:
        pass


def verify_signature(payload: bytes, signature: str) -> bool:
    secret = _github_webhook_secret()
    if not secret:
        return True
    sig = (signature or "").strip()
    if not sig.startswith("sha256="):
        logger.warning(
            "webhook signature rejected: missing or bad header (body_len=%d)",
            len(payload),
        )
        return False
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    ok = hmac.compare_digest(expected, sig)
    if not ok:
        logger.warning(
            "webhook signature mismatch: body_len=%d secret_len=%d",
            len(payload),
            len(secret),
        )
    return ok


@app.post("/deploy")
async def deploy(request: Request):
    body = await request.body()
    signature = (request.headers.get("X-Hub-Signature-256") or "").strip()

    if _github_webhook_secret() and not verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=REPO_PATH,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["bash", "./restart-screens.sh"],
            cwd=REPO_PATH,
            check=True,
            capture_output=True,
            text=True,
        )
        out = (result.stdout or "")[:200]
        send_telegram(
            "\u2705 AlphaCycle Bot deployed successfully\n\n"
            f"<code>{out}</code>"
        )
        return {"status": "deployed"}

    except Exception as e:
        send_telegram(
            "\u274c AlphaCycle Deploy FAILED\n\n"
            f"<code>{str(e)[:300]}</code>"
        )
        return {"status": "error", "detail": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok"}
