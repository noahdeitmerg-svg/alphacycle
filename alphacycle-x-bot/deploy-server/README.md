# AlphaCycle Auto-Deploy Server

Receives GitHub webhook on push, pulls latest code, restarts bot.

Uses existing `restart-screens.sh` in the bot repo (screen sessions `xbot` + `tg`). No pm2.

## Setup (VPS)

```bash
cd ~/alphacycle-repo/alphacycle-x-bot/deploy-server
pip install -r requirements.txt

# Set env vars
export GITHUB_WEBHOOK_SECRET="your-secret-here"
export BOT_REPO_PATH="/root/alphacycle-repo/alphacycle-x-bot"
export TELEGRAM_BOT_TOKEN="existing-bot-token"
export TELEGRAM_CHAT_ID="existing-chat-id"

# Start with screen (alongside xbot + tg)
screen -dmS deploy uvicorn deploy:app --host 0.0.0.0 --port 9000
```

## GitHub Setup

Settings → Webhooks → Add:

- URL: `http://95.216.152.31:9000/deploy`
- Content type: `application/json`
- Secret: same as `GITHUB_WEBHOOK_SECRET`
- Events: Just the push event

Use HTTPS / reverse proxy in production if the repo is sensitive.

## Test

```bash
curl http://95.216.152.31:9000/health
```

`POST /deploy` without a valid `X-Hub-Signature-256` returns **403** when `GITHUB_WEBHOOK_SECRET` is set.
