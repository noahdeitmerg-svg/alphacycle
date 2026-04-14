# AlphaCycle Auto-Deploy Server

Receives GitHub `push` webhook, runs `git pull` in `BOT_REPO_PATH`, then `./restart-screens.sh` (screen `xbot` + `tg`). **No pm2.**

## Schritt 1 (Cursor / Repo)

Ordner `deploy-server/` mit `deploy.py`, `requirements.txt`, dieser README ist die Quelle. Nach Aenderungen: commit + push zu `main`.

## Schritt 2 (VPS, einmalig + bei Bedarf)

SSH (ein Befehl pro Zeile — **nicht** `bashssh`):

```bash
ssh root@YOUR_VPS_IP
```

Repo und Bot (Pfade anpassen falls dein Clone woanders liegt):

```bash
cd /root/alphacycle-repo/alphacycle-x-bot
git pull origin main
```

Deploy-Server-Dependencies **im venv** (wichtig: `uvicorn` muss Modul `deploy` im Ordner `deploy-server` finden):

```bash
cd /root/alphacycle-repo/alphacycle-x-bot/deploy-server
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
deactivate
```

**Secrets und Pfade dauerhaft** (nicht nur `export` in der SSH-Session — sonst sieht `screen` sie nicht):

```bash
nano /root/deploy-server.env
```

Inhalt (Beispiel — echte Werte einsetzen):

```bash
export GITHUB_WEBHOOK_SECRET="your-long-random-secret"
export BOT_REPO_PATH="/root/alphacycle-repo/alphacycle-x-bot"
# TELEGRAM_* optional hier — siehe unten
```

- **`BOT_REPO_PATH`**: Verzeichnis mit `restart-screens.sh` und `git pull`-Ziel (Repo-Root ist **eine Ebene darueber** — `deploy.py` fuehrt `git pull` in `BOT_REPO_PATH` aus).
- **Deploy-Telegram:** `deploy.py` laedt **`TELEGRAM_BOT_TOKEN`** und **`TELEGRAM_CHAT_ID`** aus **`BOT_REPO_PATH/.env`** (dieselbe Datei wie der X-Bot), wenn dort Werte stehen — und **ueberschreibt** damit leere oder Platzhalter-Werte aus der Shell/`deploy-server.env`. Echte Token nur in **`alphacycle-x-bot/.env`** zu pflegen reicht; in `deploy-server.env` duerfen die Zeilen fehlen oder Platzhalter bleiben (nach `pip install -r` inkl. `python-dotenv`).

Alten Deploy-Prozess ggf. beenden, dann **Screen mit venv + env-Datei**:

```bash
screen -S deploy -X quit 2>/dev/null || true
# optional: orphan uvicorn auf 9000 beenden — ss -tlnp | grep 9000
screen -dmS deploy bash -lc 'cd /root/alphacycle-repo/alphacycle-x-bot/deploy-server && source .venv/bin/activate && source /root/deploy-server.env && exec uvicorn deploy:app --host 0.0.0.0 --port 9000'
screen -ls
curl -s http://127.0.0.1:9000/health
```

Erwartung: `{"status":"ok"}` und Session **`deploy`** neben **`xbot`** / **`tg`**.

**Falsch (haeufige Fehler):**

- `screen -dmS deploy uvicorn deploy:app ...` **ohne** `cd .../deploy-server` und **ohne** venv → Modul nicht gefunden oder falsche Pakete.
- Nur `export ...` in der Shell, dann `screen` ohne `source /root/deploy-server.env` in der **inneren** `bash -lc` → Webhook-Secret fehlt im Prozess.
- `curl -X POST http://localhost:9000/deploy` **ohne** GitHub-Body und **ohne** Header `X-Hub-Signature-256` → bei gesetztem Secret **403**. Test: **GET** `/health` oder echter **Push** nach GitHub.

## Schritt 3 (GitHub Webhook)

Repository → **Settings** → **Webhooks** → **Add webhook**

| Feld | Wert |
|------|------|
| Payload URL | `http://YOUR_VPS_IP:9000/deploy` |
| Content type | `application/json` |
| Secret | **identisch** zu `GITHUB_WEBHOOK_SECRET` in `/root/deploy-server.env` |
| Events | **Just the push event** |

Nach Push zu `main`: Webhook triggert Pull in `BOT_REPO_PATH` und `restart-screens.sh`; optional Telegram-Meldung aus `deploy.py`.

### 403 / „Invalid signature“ — Secret stimmt nicht

GitHub sendet `X-Hub-Signature-256`; `deploy.py` vergleicht mit **`GITHUB_WEBHOOK_SECRET`** aus dem **Prozess** (kommt aus `source /root/deploy-server.env` im Screen — siehe Schritt 2). Abweichung → **403**.

**1) VPS — Secret anzeigen (nur pruefen, nicht im Chat posten):**

```bash
ssh root@YOUR_VPS_IP
grep GITHUB_WEBHOOK /root/deploy-server.env
```

**2) GitHub — Webhook bearbeiten:** Repository → **Settings** → **Webhooks** → dein Webhook → **Edit** → **Secret**. Muss **bytegenau** wie in `deploy-server.env` sein: keine Leerzeichen am Anfang/Ende, kein Zeilenumbruch in der Zeile, keine Anfuehrungszeichen in GitHub (GitHub speichert das Secret opaque).

**3) Secret geaendert?** Deploy-Screen **neu starten** (damit der Prozess die neue env laedt) — **immer** mit venv + env-Datei (nicht nacktes `uvicorn`):

```bash
screen -S deploy -X quit 2>/dev/null || true
screen -dmS deploy bash -lc 'cd /root/alphacycle-repo/alphacycle-x-bot/deploy-server && source .venv/bin/activate && source /root/deploy-server.env && exec uvicorn deploy:app --host 0.0.0.0 --port 9000'
```

**4) Schnelltest „ist es nur der Secret-Mismatch?“** In `/root/deploy-server.env` zeitweise **`GITHUB_WEBHOOK_SECRET=""`** setzen (oder Zeile auskommentieren), Screen wie oben neu starten. In GitHub unter dem Webhook **Recent Deliveries** → fehlgeschlagene Delivery **Redeliver**. Wenn es dann **200** ist → Mismatch bestaetigt; danach **gleiches** Secret auf VPS und GitHub setzen und Screen **wieder** mit echtem Secret starten (**nicht** dauerhaft ohne Secret in Production lassen).

## Firewall

Port **9000/tcp** muss offen sein (z. B. `ufw allow 9000/tcp`).

## Production

Bei sensiblen Repos: HTTPS (Reverse Proxy) statt Klartext-HTTP fuer die Webhook-URL.

## Nach Server-Reboot (`@reboot` in crontab, einmalig)

Cron hat ein **minimales PATH** — **volle Pfade** fuer `screen`/`bash` nutzen (auf dem VPS ggf. `which screen` pruefen, meist `/usr/bin/screen`).

```bash
crontab -e
```

Zwei Zeilen (Pfade anpassen falls dein Repo woanders liegt). **Wichtig:** Deploy **nicht** mit nacktem `uvicorn` ohne venv und ohne `deploy-server.env` (Webhook-Secret).

```cron
@reboot sleep 15 && /bin/bash -lc 'cd /root/alphacycle-repo/alphacycle-x-bot && ./restart-screens.sh'
@reboot sleep 25 && /usr/bin/screen -dmS deploy bash -lc 'cd /root/alphacycle-repo/alphacycle-x-bot/deploy-server && . .venv/bin/activate && . /root/deploy-server.env && exec uvicorn deploy:app --host 0.0.0.0 --port 9000'
```

- Erste Zeile: **`xbot`** + **`tg`** (wie manuell `./restart-screens.sh`).
- Zweite Zeile: **`deploy`** etwas spaeter, damit Dateisystem/Netz nach Reboot stabil ist; gleiches Muster wie bei manuellem Screen-Start (`.venv` + **`/root/deploy-server.env`**).

**Falsch:** `@reboot ... screen -dmS deploy uvicorn deploy:app ...` **ohne** `bash -lc` mit activate + env-Datei — entspricht nicht dem laufenden Setup.

Nach naechstem Reboot pruefen: `screen -ls`, `curl -s http://127.0.0.1:9000/health`.
