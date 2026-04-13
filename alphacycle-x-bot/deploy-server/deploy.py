"""
GitHub push webhook: verify signature, git pull, restart screen sessions via restart-screens.sh.
Runs on VPS (e.g. port 9000). No pm2; Telegram notify inline only.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import subprocess

import requests
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
REPO_PATH = os.getenv("BOT_REPO_PATH", "/root/alphacycle-repo/alphacycle-x-bot")
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
    if not WEBHOOK_SECRET:
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    mac = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    )
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/deploy")
async def deploy(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "") or ""

    if WEBHOOK_SECRET and not verify_signature(body, signature):
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
