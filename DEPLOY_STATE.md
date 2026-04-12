# AlphaCycle — Deploy State
**Zuletzt aktualisiert:** 2026-04-10 (x-bot: Haiku QA Gate vor Telegram)
**Aktuelle Version:** live auf Railway (alphacycle-production.up.railway.app)

**Workflow:** Nach jeder Änderung DEPLOY_STATE.md (und ggf. .cursor/rules/permanent-fixes.mdc) aktualisieren und alle Änderungen committen und pushen. Siehe permanent-fixes.mdc Abschnitt „Nach jeder Änderung (PFLICHT)“.

## Letzter Session-Status (2026-04-10) — x-bot: Haiku QA Gate vor Telegram Approval
- **Datei(en):** `alphacycle-x-bot/prompts/qa_system.txt`, `alphacycle-x-bot/growth_engine.py` (`qa_check_reply`), `alphacycle-x-bot/bot.py` (max 2 Generate+QA Versuche), `alphacycle-x-bot/telegram_bot.py` (`send_approval` + optional `qa_pass` / Zeile `QA: PASS`), `alphacycle-x-bot/config.py` (`QA_ENABLED`, `QA_MODEL`, `QA_MAX_RETRIES`), `DEPLOY_STATE.md`, `.cursor/rules/permanent-fixes.mdc`
- **Was wurde geaendert:** Nach `generate_reply` (Sonnet) zweiter Claude-Call mit `prompts/qa_system.txt` und **QA_MODEL** (Default Haiku). Nur bei **PASS** (oder `QA_ENABLED=false`) Pending + Telegram; bei FAIL bis zu **QA_MAX_RETRIES** (2) neu generieren, sonst `qa_fail_twice`. Telegram-Info-Nachricht enthaelt bei Erfolg **QA: PASS**. Logging: `[QA] @user: PASS` / `FAIL - reason, regenerating` / `FAIL x2 - skipping tweet`.
- **Warum:** Manuelle 10+ Regeln vor Freigabe entlasten; billiger Haiku-Check.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-10) — x-bot: reply_engine Relevanz-/SKIP-Gate deaktiviert
- **Datei(en):** `alphacycle-x-bot/reply_engine.py`, `DEPLOY_STATE.md`
- **Was wurde geaendert:** Kein Abbruch mehr wenn Claude `SKIP` zurueckgibt / kein `not_relevant`-Log. User-Nachricht: immer Reply-Text, kein SKIP-Placeholder. Leere Antwort oder alleinstehendes `SKIP` (Platzhalter) -> kein Telegram-Queue. Kein separater Relevanz-Claude-Call (existierte nicht).
- **Warum:** Generierte Replies wurden nach API-Kosten verworfen; Freigabe in Telegram.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-10) — x-bot: permanent-fixes.mdc reply_engine Eintrag
- **Datei(en):** `.cursor/rules/permanent-fixes.mdc`, `DEPLOY_STATE.md`
- **Was wurde geaendert:** Dauerregel zu `reply_engine.generate_reply` (SKIP/not_relevant Gate aus, Telegram-Freigabe) ergaenzt.
- **Warum:** Abgleich mit Code-Stand e15e556; Folge auf vorherige reply_engine-Aenderung.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-10) — x-bot: reply_settings nur everyone=API sonst Copy-Paste
- **Datei(en):** `alphacycle-x-bot/bot.py` (`_infer_post_mode`), `alphacycle-x-bot/poster.py` (Log 403 ohne try_auto-Zweig), `DEPLOY_STATE.md`, `.cursor/rules/permanent-fixes.mdc`
- **Was wurde geaendert:** **everyone** -> `post_mode` **auto** (Claude -> Telegram -> `create_tweet`). Jeder andere nicht-leere Wert (**following**, **mentionedUsers**, etc.) -> **manual_only** (kein API-Versuch, nur Telegram-Zwei-Teil-Copy-Paste). Fehlendes/leeres `reply_settings` bleibt **auto** (API liefert Feld oft nicht).
- **Warum:** Kein API-Versuch bei Accounts mit eingeschraenkten Reply-Einstellungen; `try_auto` entfaellt.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — x-bot: mehr Reply-Candidates (Limits, SKIP-Prompt, Logging)
- **Datei(en):** `alphacycle-x-bot/config.py`, `alphacycle-x-bot/scanner.py`, `alphacycle-x-bot/reply_engine.py`, `DEPLOY_STATE.md`
- **Was wurde geaendert:** `MAX_REPLIES_PER_HOUR` **10**, `MAX_REPLIES_PER_DAY` **30**, `REPLY_DELAY_MIN/MAX` **30–120** s, `MIN_LIKES_TO_REPLY` Default **0** (weiter per `.env` steuerbar). `BLOCKED_KEYWORDS` **temporaer leer** fuer Test-Durchsatz. `reply_engine`: User-Prompt lockert SKIP (nur offensichtlich irrelevant); `logger.info` bei `not_relevant`. `scanner`: `logger.info` bei Skip mit Grund (`too_recent`, `too_old`, `low_likes`, `blocked_keyword`, `already_scanned`, `already_replied`, `same_account_limit` fuer spacing + daily cap).
- **Warum:** Zu viele Candidates wurden als nicht-ARC-relevant verworfen bzw. zu wenig Tweets passierten Likes/Filter.
- **Status:** pushed to GitHub (VPS: `git pull` + `restart-screens.sh`)

## Letzter Session-Status (2026-04-11) — docs: 5 ARC-Zonen ueberall konsistent (Doku only)
- **Datei(en):** `CURSOR_MASTERPROMPT.md` (alte 4-Stufen 61/81 entfernt; Tabelle 0-29 … 70-100 + Verweise), `docs/alphacycle_context.md` (2.4 Boundary Implementation neu), `docs/alphacycle_ai_operating_manual.md`, `docs/alphacycle_ai_operating_manual_COMPLETE.md` (Section 2 Locked Constants), `DEPLOY_STATE.md`
- **Was wurde geaendert:** Zonen-Doku aligned mit `get_zone_name` / `phaseOf` / `scoreColor`; veraltete FIX-1/2/3- und OKX-„todo“-Zeilen im Masterprompt bereinigt; Datenquellen-Tabelle OKX auf live gesetzt.
- **Warum:** Eine klare, widerspruchsfreie Beschreibung des 5-Zonen-Modells.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — docs: ARC-Formel auf Live abgleichen (scoring.py)
- **Datei(en):** `docs/alphacycle_ai_operating_manual.md`, `docs/alphacycle_ai_operating_manual_COMPLETE.md`, `AlphaCycle-AI-Manual-Sections-11-13-FINAL-v2.md`, `CURSOR_MASTERPROMPT.md`, `DEPLOY_STATE.md`
- **Was wurde geaendert:** Section 11/12 ARC-Zeile und LOCKED-Block: **ma_200w×0.35 + drawdown×0.25 + liquidity×0.25 + fear_greed×0.15** (wie `compute_arc_score`). Fruehere 0.30/0.20-Gewichte entfernt. `CURSOR_MASTERPROMPT.md` Formel ebenfalls korrigiert.
- **Warum:** Doku entspricht Production; keine Aenderung an Backend-Code.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — docs: Operating Manual Sections 11-13 eingepflegt (kein Code)
- **Datei(en):** `docs/alphacycle_ai_operating_manual.md`, `docs/alphacycle_ai_operating_manual_COMPLETE.md` (identischer Volltext), Quelle `AlphaCycle-AI-Manual-Sections-11-13-FINAL-v2.md`, `DEPLOY_STATE.md`
- **Was wurde geaendert:** Abschnitte **11–13** (Signal Architecture, AI Agent Initialization, Long-Term Vision) vollstaendig ans Ende des bestehenden Manuals angehaengt; Sections **1–10** unveraendert. Zusaetzliche Kopie `alphacycle_ai_operating_manual_COMPLETE.md` mit gleichem Inhalt.
- **Warum:** Ein Dokument fuer AI-Betrieb und Langzeit-Positionierung.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — docs: alphacycle_ai_operating_manual.md + README (kein Code)
- **Datei(en):** `docs/alphacycle_ai_operating_manual.md` (von Repo-Root nach `docs/` verschoben, falls vorher nur lokal im Root), `README.md` (Hinweis oben: Operating Manual + `alphacycle_context.md`), `DEPLOY_STATE.md`, `.cursor/rules/permanent-fixes.mdc`
- **Was wurde geaendert:** AI Operating Manual als Doku unter `docs/`; README verweist auf Manual und Kontext-Datei. Keine Code-Aenderungen.
- **Warum:** Zentrale Agent-Rollen, Dev-Regeln und Masterprompt-System fuer AI-Sessions.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — x-bot: reply_system.txt + post_system.txt komplett ersetzt (kurz, Compliance)
- **Datei(en):** `alphacycle-x-bot/prompts/reply_system.txt`, `alphacycle-x-bot/prompts/post_system.txt`, `DEPLOY_STATE.md`, `.cursor/rules/permanent-fixes.mdc`
- **Was wurde geaendert:** Beide Master-Prompts **vollstaendig** durch kuerzere Versionen ersetzt (ca. Haelfte der alten Laenge): kritische Regeln oben und unten, klare Limits (Reply **260** Zeichen im Prompt, Post max **2** Datenpunkte, keine Vorhersagen, Banned-Woerter/ kein deklarativer Fluff). Platzhalter fuer `growth_engine` unveraendert (`{arc_data_block}`, `{approach}`, `{reply_pattern}`, etc.). **Kein** Code in `growth_engine.py` / `reply_engine.py` geaendert (Clip weiter 270 Zeichen).
- **Warum:** Lange Prompts wurden von Claude teils ignoriert; kuerzer soll Regelbefolgung verbessern.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — Repo: docs/ + alphacycle_context.md (AI Single Source of Truth)
- **Datei(en):** `docs/alphacycle_context.md` (Inhalt aus ehem. Repo-Root verschoben), `README.md` (Hinweis ganz oben), `DEPLOY_STATE.md`, `.cursor/rules/permanent-fixes.mdc`
- **Was wurde geaendert:** Ordner **`docs/`** mit zentralem Kontextdokument; Root-`alphacycle_context.md` entfernt (eine kanonische Datei unter `docs/`). Keine Code-Aenderungen. `alpha_cycle_whitepaper.pdf`, `system_map.png`, `roadmap.md` im Root nicht vorhanden — kein Move.
- **Warum:** Klarer Einstieg fuer AI/Entwickler-Sessions.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — x-bot: Scanner — mehr Kandidaten (MAX_TWEET_AGE default 6h)
- **Datei(en):** alphacycle-x-bot/config.py (`MAX_TWEET_AGE_SECONDS` default **21600**, `MIN_TWEET_AGE_SECONDS` per Env), alphacycle-x-bot/bot.py (Log-Hinweis wenn 0 Kandidaten), alphacycle-x-bot/scanner.py (Scan-Zeile mit Fenster/Likes), alphacycle-x-bot/.env.example, DEPLOY_STATE.md
- **Was wurde geaendert:** Vorher nur Tweets der **letzten 3600s** (1h) — zu eng fuer `/scan` ohne Treffer. Default jetzt **6h**; alles per `MAX_TWEET_AGE_SECONDS` / `MIN_LIKES_TO_REPLY` / `MIN_TWEET_AGE_SECONDS` in `.env` steuerbar.
- **Warum:** Nutzer: 50 Accounts gescannt, aber keine passenden Tweets; typisch zu kurzes Altersfenster + Mindest-Likes + Abstands-/Tageslimits.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-11) — x-bot: TRACKED_ACCOUNTS Zahl korrigiert (50, nicht 60)
- **Datei(en):** alphacycle-x-bot/config.py (Kommentare), DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Klarstellung: **10+20+20 = 50** Handles in `TRACKED_ACCOUNTS`; fruehere „60“-Angabe war ein Rechen-/Doku-Fehler. Read-Budget-Kommentar an 50*24 angepasst.
- **Warum:** VPS `len(config.TRACKED_ACCOUNTS)` ergab 50 — erwartetes Ergebnis fuer die committed Listen.
- **Status:** pushed to GitHub

## Letzter Session-Status (2026-04-10) — x-bot: Viral Reply Patterns (Growth Engine + DB)
- **Datei(en):** alphacycle-x-bot/config.py (`REPLY_PATTERNS` Gewichte), alphacycle-x-bot/growth_engine.py (`select_pattern_key`, Streak-Vermeidung letzte 2 gleiche Patterns, `{reply_pattern}`-Injection, Logging), alphacycle-x-bot/prompts/reply_system.txt (Block REPLY PATTERN), alphacycle-x-bot/reply_engine.py (3-Tupel), alphacycle-x-bot/bot.py / poster.py / telegram_listener.py (pattern durchreichen), alphacycle-x-bot/database.py (`pattern` auf `reply_history` + `pending_replies`, `get_last_reply_patterns`, `save_reply`/`insert_reply_history`/`insert_pending_reply`), DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Zusaetzlich zu den 5 Approaches rotieren vier strukturelle Patterns (contrarian_insight_hook, cycle_reframe, historical_memory, structural_insight). Prompt enthaelt `{reply_pattern}` mit vollem Muster-Text. Wenn die letzten zwei `reply_history`-Patterns identisch sind, wird bei Bedarf ein anderes Pattern gewaehlt. `generate_reply` liefert `(text, approach, pattern)`; Pending und `insert_reply_history` speichern `pattern`.
- **Warum:** Mehr Variation und klarere Schreib-Rahmen ohne die bestehenden Brand-/Banned-Regeln zu lockern.
- **Status:** pushed to GitHub; VPS: git pull + restart-screens

## Letzter Session-Status (2026-04-10) — x-bot: Dashboard-Banner Screenshot (1500x500) + X-Header + Telegram
- **Datei(en):** alphacycle-x-bot/generate_banner.py (neu), alphacycle-x-bot/bot.py (`_weekly_banner_job`, So 12:00), alphacycle-x-bot/telegram_listener.py (`/banner`, Text `banner`, `menu:banner`), alphacycle-x-bot/telegram_bot.py (`send_photo_path`), alphacycle-x-bot/requirements.txt (playwright, Pillow), alphacycle-x-bot/banners/.gitkeep, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Playwright oeffnet `alphacycle.app` (Viewport 1600x900), wartet auf `#btc-score-val` numerisch, Screenshot, Crop/Resize auf **1500x500**, optional **Tweepy v1.1** `update_profile_banner`. CLI: `python generate_banner.py`. **bot.py:** woechentlich Sonntag **12:00** (Prozess-TZ wie Daily = UTC wenn `TZ=UTC`+tzset). **Telegram:** `/banner` oder Wort `banner` oder Menue-Button; generiertes PNG als Foto + Upload-Status. Env: `BANNER_PAGE_URL`, `BANNER_OUTPUT_DIR` optional.
- **Warum:** X-Profil-Header aus live Dashboard ohne manuelles Zuschneiden.
- **VPS:** `pip install -r requirements.txt`, **`playwright install chromium`** (~150MB), ggf. System-Deps; Read+Write fuer Banner-Upload.
- **Status:** pushed to GitHub; VPS: `pip install -r requirements.txt`, `playwright install chromium`, git pull, `./restart-screens.sh`

## Letzter Session-Status (2026-04-10) — x-bot: TRACKED_ACCOUNTS Tier-Listen + Scan-Default 60 Min
- **Datei(en):** alphacycle-x-bot/config.py, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** `TIER_1`/`TIER_2`/`TIER_3` + `TRACKED_ACCOUNTS` (Summe **50** Handles). `BLOCKED_KEYWORDS` erweitert. Default `SCAN_INTERVAL_SECONDS` **3600**. *(Fruehere „60 Accounts“-Formulierung war falsch — siehe Eintrag 2026-04-11.)*
- **Warum:** Mehr Reply-Ziele; laengeres Scan-Intervall fuer Read-Budget.
- **Status:** pushed to GitHub; VPS: git pull + `restart-screens.sh`

## Letzter Session-Status (2026-04-10) — x-bot: poster.py Reply — immer Telegram Copy-Paste bei API/Limit
- **Datei(en):** alphacycle-x-bot/poster.py, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** `_send_manual_copy_paste`: einheitliches Format (Tweet-Link, Reply in Trennlinien, Schritte 1–3, `[MANUAL_REPLY]`); zuerst `telegram_bot.send_feedback_message`, bei Fehler Raw-HTTP-Backup mit `r.ok`-Pruefung und Logging. `_post_reply_impl`: bei **Bot** Stunden-/Tageslimit kein stilles `"failed"` mehr — stattdessen manuelle Telegram-Nachricht und Rueckgabe `"manual"` (ohne `mark_api_blocked_account`, da kein X-Account-Block). Alle X-/OAuth-Fehlerpfade mit `logger.warning`/`logger.error`; unerwartetes `"failed"` nach `_post_reply_impl` mit Sicherheits-Fallback.
- **Warum:** Listener zeigte „fehlgeschlagen“ ohne sichtbaren Copy-Paste-Text, wenn nur das interne Limit griff oder Telegram-Sendung still scheiterte.
- **Status:** pushed to GitHub; VPS: git pull + `restart-screens.sh` zum Live-Schalten

## Letzter Session-Status (2026-04-10) — x-bot: reply_system Banned+LOGIC, max 2 Replies/Account/Tag (UTC)
- **Datei(en):** alphacycle-x-bot/prompts/reply_system.txt (BANNED erweitert; LOGIC CHECK nach FACTUAL), alphacycle-x-bot/database.py (`count_replies_to_author_today_utc`), alphacycle-x-bot/scanner.py (Skip + Log `[SCANNER] Skipping @...`), DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Prompt: keine "flip the script" / "speaks volumes" etc.; Logik-Regeln gegen widersprüchliche oder falsche Ironie (bullish an Tiefs = smart). Scanner: `reply_history` zaehlt pro Autor pro **UTC-Kalendertag**; ab 2 Eintraegen kein neuer Candidate, `skipped_reason` `daily_reply_limit`.
- **Warum:** Weniger Tone-Deafness; weniger Spam pro Handle pro Tag.
- **Status:** deployed (VPS: git pull + restart-screens; Railway nur wenn Backend betroffen — hier nicht)

## Letzter Session-Status (2026-04-10) — arc-summary btc_price/btc_ath + Reply-Prompt aus API
- **Datei(en):** backend/main.py (`/api/arc-summary` Felder `btc_price`, `btc_ath` wie Cache/Kraken+btc_market.ath), alphacycle-x-bot/daily_post_engine.py (`btc_ath` durchreichen), alphacycle-x-bot/growth_engine.py (`_format_arc_block`), alphacycle-x-bot/prompts/reply_system.txt, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** ATH/Spot kommen aus demselben Backend wie das Dashboard; `{arc_data_block}` enthaelt explizite Zeilen fuer ATH und Drawdown %. Reply-Prompt verweist nur noch auf CURRENT DATA, keine feste USD-Zahl.
- **Warum:** ATH aendert sich; eine Quelle (API) vermeidet Drift.
- **Status:** deployed (Railway Backend deploy + VPS x-bot git pull / restart-screens)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: reply_system ATH Referenz 126k
- **Datei(en):** alphacycle-x-bot/prompts/reply_system.txt, DEPLOY_STATE.md
- **Was wurde geaendert:** FACTUAL ACCURACY Zeile: ATH von ~108k auf ~126k USD (Cycle-Top Okt 2025).
- **Warum:** Nutzerkorrektur; konsistent mit ca. 126k ATH.
- **Status:** deployed (VPS: git pull + restart-screens)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: reply_system.txt komplett + Reply-Abstand pro Account
- **Datei(en):** alphacycle-x-bot/prompts/reply_system.txt (voller Ersatz), alphacycle-x-bot/database.py (`is_author_spacing_ok_for_reply` via `reply_history`), alphacycle-x-bot/scanner.py (`author_spacing` Skip), alphacycle-x-bot/reply_engine.py (Clip 270 Zeichen), DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Neuer Master-Reply-Prompt: 270-Zeichen-Regel, Banned-Words, Bar-Test, Good/Bad Beispiele, erste Satz auf deren Tweet, ATH/F&G-Checks im Text; keine AlphaCycle/ARC im Output. Scanner: kein Candidate fuer einen Account bis mindestens zwei **andere** Accounts in neueren `reply_history`-Zeilen seit dem letzten Reply an diesen Account. Engine clippt auf 270 Zeichen.
- **Warum:** Weniger kaputte/abgeschnittene Replies, weniger akademischer Ton, kein Spam auf denselben Handle hintereinander.
- **Status:** deployed (VPS: git pull, `./restart-screens.sh`)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Telegram Hauptmenue (Inline-Buttons + menu:*)
- **Datei(en):** alphacycle-x-bot/telegram_bot.py (`send_main_menu`), alphacycle-x-bot/telegram_listener.py (`menu:*`, `_MENU_TRIGGERS`, `/menu`), alphacycle-x-bot/RUN_24_7.md, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** `/start` und `/menu` senden eine Nachricht mit Erklaertext und Inline-Tasten (Status, Ping, Scan, Daily-Queue, Screen-Logs, Menue erneut, Hilfe). Callbacks `menu:…` fuehren dieselben Aktionen wie die Slash-Befehle. `/help` sendet Menue plus Befehlsliste. Schlagwoerter z. B. `menu`, `hilfe`, `hallo` oeffnen das Menue (nur autorisierter Chat).
- **Warum:** Steuerung komplett ueber tippen ohne Slash merken zu muessen.
- **Status:** deployed (VPS: git pull, `./restart-screens.sh`)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: restart-screens.sh (mehrere tg/xbot Sockets)
- **Datei(en):** alphacycle-x-bot/restart-screens.sh, alphacycle-x-bot/RUN_24_7.md, DEPLOY_STATE.md
- **Was wurde geaendert:** Skript beendet alle Screen-Sockets der Form `*.xbot` und `*.tg` per eindeutiger ID (`12345.tg`), startet danach genau eine `xbot`- und eine `tg`-Session — vermeidet GNU-Screen-Meldung „several suitable screens“ wenn `screen -S tg -X quit` mehrdeutig war.
- **Warum:** Nach fehlgeschlagenem Quit stapelten sich mehrere `tg`-Prozesse; `/logtg` und Telegram-Callbacks verhalten sich dann unklar.
- **Status:** deployed (VPS: git pull, `chmod +x restart-screens.sh`, `./restart-screens.sh`)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Telegram ohne Laptop (/scan, /queuedaily, /logbot, /logtg)
- **Datei(en):** alphacycle-x-bot/telegram_listener.py, alphacycle-x-bot/config.py (`SCREEN_SESSION_BOT` / `SCREEN_SESSION_TG`), alphacycle-x-bot/.env.example, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Slash-Befehle nur fuer `TELEGRAM_CHAT_ID`: `/scan` startet `bot.py --once`, `/queuedaily` startet `bot.py --queue-daily`, `/logbot` und `/logtg` holen Scrollback per `screen -S ... -X hardcopy -h` (Session-Namen per Env, Default xbot/tg). Callbacks POST/SKIP/dpost/dskip ebenfalls nur autorisierte Chat-ID. `done`-Flow nur autorisiert. Hilfe-Text erweitert.
- **Warum:** Betrieb komplett vom Handy in Telegram ohne SSH/screen -r zum Lesen der Logs.
- **Status:** deployed (VPS: git pull, beide Screen-Sessions neu starten falls noetig; `.env` optional `SCREEN_SESSION_BOT` / `SCREEN_SESSION_TG` wenn andere Session-Namen)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: post_system.txt CRITICAL STYLE (deklarativ + Datenpunkt-Zaehlung)
- **Datei(en):** alphacycle-x-bot/prompts/post_system.txt, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** CRITICAL STYLE RULES: deklarative Muster (This is/That is + Erklaerung) explizit verboten; Datenpunkt-Limit mit Pflicht-Zaehlung vor Output und Beispiel (drei = schwaechsten streichen); FINAL TEST Punkt 5 angepasst.
- **Warum:** Weniger Broschueren-Saetze, weniger Daten-Dumps in Daily Posts.
- **Status:** deployed (VPS: git pull; Daily neu generieren nutzt neuen Prompt)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Zwei-Stufen Reply System (API -> Telegram Copy/Paste)
- **Datei(en):** alphacycle-x-bot/poster.py, alphacycle-x-bot/database.py, alphacycle-x-bot/telegram_listener.py, DEPLOY_STATE.md
- **Was wurde geaendert:** Reply-Post versucht zuerst X API. Bei 401/403/sonstigem X-Fehler (oder vorherigem Blocklist-Treffer <7 Tage) geht der Bot sofort in einen Telegram-Copy/Paste-Flow mit direktem Tweet-Link + Reply-Text; betroffene Accounts landen in `api_blocked_accounts` (7-Tage-Window, danach Retry). Nach manuellem Post kann per Antwort `done` auf die Copy/Paste-Nachricht die Reply in `reply_history` als gepostet markiert werden.
- **Warum:** X Anti-Spam blockt Replies auf grosse Accounts; manueller Fallback verhindert, dass starke Replies komplett verloren gehen.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Daily Post Claude 529 sofort Haiku-Fallback
- **Datei(en):** alphacycle-x-bot/config.py (`CLAUDE_MODEL_DAILY_FALLBACK`, Env, `none` schaltet Fallback aus), alphacycle-x-bot/daily_post_engine.py (`generate_daily_post`: Primary 529 dann sofort Fallback, sonst wie bisher 3 Runden mit 10-20 min Sleep), alphacycle-x-bot/.env.example, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Anthropic 529 ist Server-Ueberlast, kein App-Bug; bei Ueberlast auf Sonnet wird unmittelbar ein zweites Modell versucht, damit der Daily-Post nicht nur stundenlang wartet.
- **Warum:** Hauefig nur eine Modell-Sparte ueberlastet; Fallback erhoeht Erfolgsquote ohne Reply-Pipeline zu aendern.
- **Status:** deployed (VPS: git pull + Screen neu starten)

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: bot_runtime Status + --queue-daily
- **Datei(en):** alphacycle-x-bot/database.py (`bot_runtime`, `set_bot_booted_now`, `record_scan_cycle_finished`, `get_bot_runtime_status`), alphacycle-x-bot/bot.py (`run_cycle` finally, `set_bot_booted_now`, CLI `--queue-daily`), alphacycle-x-bot/telegram_listener.py (`/status` nutzt DB), DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Uptime (h seit Prozess-Start), Scans today (abgeschlossene Scan-Zyklen UTC-Tag), Last scan (UTC) persistiert; Catch-up: `python3 bot.py --queue-daily` baut Daily und Telegram-Freigabe ohne Scheduler-Loop (Main-Bot parallel ok).
- **Warum:** /status vollstaendiger; fehlgeschlagener Daily (z. B. 529) manuell nachholen.
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: generate_daily_post Retry bei Claude 529 overloaded
- **Datei(en):** alphacycle-x-bot/daily_post_engine.py, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** `generate_daily_post`: bis zu 3 Anthropic `messages.create`-Versuche; bei 529/overloaded_error Pause random 600-1200s (10-20 min) vor erneutem Versuch. Andere API-Fehler: sofortiger Abbruch wie bisher.
- **Warum:** Hauefiger `overloaded_error` loeste leere Daily-Queue aus; Scheduler-Job kann waehrend der Pause blockieren (einmal taeglich akzeptabel).
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: Telegram Post-Bestaetigung + /status + Daily Summary 23:00 UTC
- **Datei(en):** alphacycle-x-bot/poster.py, alphacycle-x-bot/telegram_listener.py, DEPLOY_STATE.md, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Nach erfolgreichem Reply/Daily-Post: Telegram an TELEGRAM_CHAT_ID mit Link `x.com/Real_AlphaCycle/status/{neue_tweet_id}` (ID aus create_tweet-Response). `/status` liefert Metriken aus SQLite (replies today/hour, candidates aus `scanned` ohne skip reason, next daily UTC) sowie n/a fuer Uptime/Scans/Last scan (kein bot.py-State). Jeden UTC-Tag um 23:00 automatisch Daily Summary (Posts aus `posted_topics`, Replies, Impressions n/a, Candidates).
- **Warum:** Betriebstransparenz ohne zusaetzliche DB-Aenderungen.
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: TIER_2 coinabormetrics_io → coinmetrics
- **Datei(en):** alphacycle-x-bot/config.py, DEPLOY_STATE.md
- **Was wurde geaendert:** Handle `coinabormetrics_io` durch offizielles `coinmetrics` (Coin Metrics) ersetzt.
- **Warum:** User-verifizierter korrekter X-Handle.
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: TIER_3 ChrisBurniske → cburniske
- **Datei(en):** alphacycle-x-bot/config.py, DEPLOY_STATE.md
- **Was wurde geaendert:** `ChrisBurniske` durch `cburniske` ersetzt (korrekter X-Handle). `willywoo`, `BitcoinMagazine`, Entfernung `glasabornode` waren bereits im Stand vom letzten Commit.
- **Warum:** User-verifizierte Handles.
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: TRACKED_ACCOUNTS Handle-Korrekturen (TIER_2)
- **Datei(en):** alphacycle-x-bot/config.py
- **Was wurde geaendert:** `glasabornode` entfernt (Tippfehler/nicht existent). Ersatz: `BitcoinMagazine`. `woonomic` → `willywoo` (oeffentliche X-Einbettungen Maerz 2026 zeigen @willywoo fuer Willy Woo; „woaboronomic“ im Ticket keine plausibler Handle — bei API-404 auf VPS ggf. `woonomic` oder `id:USER_ID` einsetzen). `coinmetrics` → `coinabormetrics_io` laut Vorgabe (offizieller CM-Account ist @coinmetrics; wenn Lookup scheitert, Handle pruefen oder `id:`).
- **Warum:** Scanner soll nur gueltige Accounts tracken; gleich 25 Eintraege (5+12+8).
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: TRACKED_ACCOUNTS 25 + TIER_3 + BLOCKED_KEYWORDS
- **Datei(en):** alphacycle-x-bot/config.py
- **Was wurde geaendert:** TIER_1 (5), TIER_2 (12), neu TIER_3 (8); `TRACKED_ACCOUNTS` = Summe aller drei (25); `BLOCKED_KEYWORDS` erweitert (u.a. 1000x, PUMP, giveaway, airdrop, presale, whitelist, JOIN NOW, FREE MINT, LAST CHANCE). Scanner/Reply-Code unveraendert.
- **Warum:** Fokussierte Reply-Ziele laut Produktliste; mehr Noise-Filter.
- **Deploy-Hinweis:** Mehrere Handles vor Live-Betrieb in X pruefen (woonomic, ecoinometrics, coinmetrics, stackhodler, therationalroot, TXMCtrades, MacroCharts, GameofTrades_, fejau_inc, CryptoHayes, ChrisBurniske, MacroAlf; TIER_2-Eintrag `glasabornode` auf Schreibweise pruefen). Verifiziert laut Nutzerliste: RaoulGMI, LynAldenContact, KobeissiLetter, 100trillionUSD, WClemente, _Checkmatey_, in2cryptoversee, DylanLeClair, CryptoCon_, TechDev_52, PositiveCrypto, GlassnodeAlerts.
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: reply_system.txt komplett ersetzt (Master-Reply-Prompt)
- **Datei(en):** alphacycle-x-bot/prompts/reply_system.txt (voller Ersatz: CURRENT MARKET CONTEXT, erweiterte Approaches, Hook-Phrasen 40/60, FACTUAL ACCURACY, CRITICAL REPLY RULES, Beispiele, ANTI-AI, FINAL TEST; Platzhalter `{arc_data_block}` `{approach}` `{hook_instruction}` `{tweet_author}` `{tweet_text}` `{reply_history}` unveraendert), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Reply-Operating-Brain 1:1 wie Spec; laenger; `build_reply_prompt`/`growth_engine` unveraendert (ACTIVE/INACTIVE fuer `{hook_instruction}`).
- **Warum:** Schärfere X-Replies, Profil-Curiosity, weniger AI-Ton.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: post_system.txt komplett ersetzt (Master-Prompt)
- **Datei(en):** alphacycle-x-bot/prompts/post_system.txt (voller Ersatz: Identity, ARC-Zonen, Three Lens, CURRENT MARKET CONTEXT, FACTUAL ACCURACY, Narrativ-Arc, Share Lines, Zone Taglines, CRITICAL STYLE, ABSOLUTE PROHIBITIONS, Beispiel-Posts, FINAL TEST; Platzhalter `{arc_data_block}` `{post_type}` `{posted_topics}` unveraendert), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Operating-Brain Daily-Post-Prompt 1:1 wie Spec; deutlich laenger; Hinweis: Zeile „LAST 7 DAYS“ im Text, technisch weiter `get_recent_topics(TOPIC_LOOKBACK_DAYS)`.
- **Warum:** Einheitlicher, schaerferer Daily-Post-Stil inkl. Beispiele und Kontextblock.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: post_system Fakten-Sicherung
- **Datei(en):** alphacycle-x-bot/prompts/post_system.txt (CRITICAL STYLE: FACTUAL ACCURACY, Pflicht-Zahl aus ARC-Daten, kein „This is how X works“), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Narrativ muss zu Fear&Greed/ATH/Preis passen; mind. eine konkrete Zahl aus ARC-Daten natuerlich im Text; „numbers test“ an Pflicht-Zahl + max zwei Datenpunkte angepasst.
- **Warum:** Keine erfundene Stimmung, keine Textbuch-Saetze.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: post_system CRITICAL STYLE (Erweiterung)
- **Datei(en):** alphacycle-x-bot/prompts/post_system.txt, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** CRITICAL STYLE RULES ergaenzt: kein Sales-Talk („maximum opportunity“), Phasen nicht deklarativ erklaeren (Beobachtung/Kontrast), Zonennamen max. einmal eingebettet kein Label, keine Em-Dashes zwischen Dramen (Zeilenumbrueche).
- **Warum:** Analysten-Ton, weniger Broschuere, klarere X-Lesbarkeit.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: post_system CRITICAL STYLE RULES
- **Datei(en):** alphacycle-x-bot/prompts/post_system.txt (CRITICAL STYLE RULES vor „Write the post now“; RULES-Bullet „at most two data points“ statt „one number“), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Schaerfere Daily-Post-Vorgaben: max zwei Datenpunkte, Dollar voll ausgeschrieben, keine Return-/Win-Rate-Zahlen im Tweet, kein exakter ARC-Score (Zone/Perzentil), Narrativ/Micro-Story, ATH-„new highs“-Check, Insight vor Information.
- **Warum:** Weniger Daten-Dumps, staerkerer X-Ton.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: pending_daily_posts.arc_score + save_topic
- **Datei(en):** alphacycle-x-bot/database.py (`pending_daily_posts.arc_score` REAL, Insert/Select), alphacycle-x-bot/bot.py (`_arc_score_for_pending`, Insert), alphacycle-x-bot/poster.py (`_arc_score_int_for_save_topic`, Fallback `fetch_arc_data`), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** ARC-Rohscore beim Daily-Queue in DB; `save_topic` bekommt gerundeten Integer aus Pending-Zeile oder frischen Fetch.
- **Warum:** posted_topics.arc_score fuer Auswertung/Prompt-Kontext statt immer NULL.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: build_post_prompt get_recent_topics + save_topic nach Daily
- **Datei(en):** alphacycle-x-bot/growth_engine.py (`build_post_prompt` laed `database.get_recent_topics`, Logging), alphacycle-x-bot/daily_post_engine.py (`summarize_post_one_sentence`, `generate_daily_post` -> Tuple + UTC weekday), alphacycle-x-bot/poster.py (`save_topic` nach erfolgreichem Daily), alphacycle-x-bot/database.py (`pending_daily_posts.post_type`), alphacycle-x-bot/bot.py (`insert_pending_daily_post` mit Typ, `logging.basicConfig` INFO), prompts/post_system.txt, permanent-fixes.mdc
- **Was wurde geaendert:** `{posted_topics}` im Post-Prompt aus Tabelle `posted_topics` (Lookback TOPIC_LOOKBACK_DAYS), Zeilen `summary (type)`; nach Daily-Post auf X: Claude 1-Satz-Summary + `save_topic`; `post_type` beim Queue in DB gespeichert.
- **Warum:** Keine Wiederholung frueherer Winkel; persistente Topic-Zeilen fuer naechste Prompts.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: ARC_API_URL Railway (JSON fix)
- **Datei(en):** alphacycle-x-bot/config.py (`ARC_API_URL` + `ALPHACYCLE_PUBLIC_BASE` Default Railway; `ARC_API_URL` per `ARC_API_URL` env), alphacycle-x-bot/daily_post_engine.py (JSON-Fetch-Fallback-Host Railway statt alphacycle.app), alphacycle-x-bot/.env.example, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Default Arc-Summary = `https://alphacycle-production.up.railway.app/api/arc-summary` — `alphacycle.app/api/arc-summary` liefert SPA-HTML, Bot brauchte JSON (`Expecting value` auf VPS).
- **Warum:** Scan-Zyklus und Daily-Post `fetch_arc_data` wieder funktionsfaehig ohne manuelle .env-Pflicht.
- **VPS:** Optional weiterhin `ARC_API_URL=...` in `.env` setzen; `git pull` + Bot/Listener neu starten.
- **Status:** deployed

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Telegram Chat-Feedback + Commands
- **Datei(en):** alphacycle-x-bot/telegram_bot.py (`send_feedback_message`, `answer_callback_query` show_alert-Param), alphacycle-x-bot/telegram_listener.py (Bestätigungsnachricht als Reply auf Freigabe-Karte; /status /ping /help /start)
- **Was wurde geaendert:** Nach jedem Button-Druck zusätzliche sichtbare Nachricht im Chat (wer was gedrückt hat, Tweet-ID/Pending-ID, Ergebnis); kurzer Callback-Toast unveraendert.
- **Warum:** Nutzer wollte klare Rueckmeldung neben dem kurzen Toast oben.
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: config ARC_API_URL, tiers, scanner blocked
- **Datei(en):** alphacycle-x-bot/config.py (`ARC_API_URL`, `DAILY_POST_TIME`, `REPLY_HOOK_PROBABILITY`, `MAX_REPLY_HISTORY`, `TOPIC_LOOKBACK_DAYS`, `CLAUDE_MODEL`, `TIER_1/2_ACCOUNTS`, `TRACKED_ACCOUNTS` Union, `BLOCKED_KEYWORDS`), growth_engine.py, reply_engine.py, bot.py, daily_post_engine.py, database.py (`TOPIC_LOOKBACK_DAYS` in daily topics query), scanner.py, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Zentrale Config-Keys laut Spec; `fetch_arc_data` nutzt `ARC_API_URL` + Host-Parsing; Scheduler `DAILY_POST_TIME`; Hook/History aus Config; Daily-Topic-Lookback; Scanner filtert `BLOCKED_KEYWORDS` mit `log_scanned(..., blocked_keyword)`; Track-Liste = Tier-1+2 (ohne fruehere CryptoCapo/CryptoCred/id-Liste).
- **Warum:** Einheitliche Steuerung; klarere Ziel-Accounts; weniger Hype-Tweets in der Queue.
- **Hinweis:** „Nur Tier + Accounts mit >10K Followern“ ist noch nicht implementiert (nur Config/Keyword-Filter + Tier-Union).
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: database reply_history + posted_topics
- **Datei(en):** alphacycle-x-bot/database.py (`reply_history` Schema tweet_text/had_hook/timestamp, `posted_topics`, `get_recent_replies`, `save_reply`, `get_recent_topics`, `save_topic`, `_upgrade_reply_history_schema`, `insert_reply_history` angepasst), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** `reply_history` laut Spec; neue Tabelle `posted_topics`; bestehende Tabellen (replies, scanned, …) unveraendert; Legacy-DBs: fehlende Spalten per ALTER + timestamp aus created_at; Sortierung kompatibel mit/ohne created_at.
- **Warum:** Reichere Reply-Logs und Topic-Tracking fuer Posts (topic_summary spaeter via Claude).
- **Status:** deployed

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: Daily Post Scheduler + pending_daily_posts
- **Datei(en):** alphacycle-x-bot/bot.py (`schedule`, `schedule_daily_post`, 60s loop + `SCAN_INTERVAL_SECONDS` fuer `run_cycle`), alphacycle-x-bot/database.py (`pending_daily_posts`, CRUD), alphacycle-x-bot/telegram_bot.py (`send_daily_post_approval`), alphacycle-x-bot/telegram_listener.py (`dpost:`/`dskip:`), alphacycle-x-bot/poster.py (`post_daily_post`, `record_daily_post_topic`), alphacycle-x-bot/requirements.txt (`schedule`), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Taeglich 13:00 (UTC wenn TZ=UTC/tzset): `fetch_arc_data` + `generate_daily_post`, Telegram-Freigabe, POST via `create_tweet` ohne Reply; SKIP loggt/ueberspringt; bei `fetch_arc_data` None nur Warning kein Queue.
- **Warum:** Daily Post zusaetzlich zum Reply-Scanner ohne Auto-Post.
- **Status:** in progress

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: reply_engine + reply_history + approach
- **Datei(en):** alphacycle-x-bot/reply_engine.py, alphacycle-x-bot/growth_engine.py (`build_reply_prompt` -> tuple mit `approach_key`), alphacycle-x-bot/database.py (`reply_history`, `get_reply_history_texts_for_prompt`, `insert_reply_history`, `pending_replies.approach`), alphacycle-x-bot/bot.py (`daily_post_engine.fetch_arc_data`, `generate_reply` Tuple, `insert_pending_reply` mit approach), alphacycle-x-bot/poster.py (`insert_reply_history` nach Post), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Reply-Prompt nur noch via `build_reply_prompt`; ARC aus `fetch_arc_data`; History aus `reply_history` (Fallback `replies`); nach erfolgreichem Post Eintrag in `reply_history` inkl. Approach; Approach in `pending_replies` fuer Telegram-Queue.
- **Warum:** Growth-Engine-Integration laut Spec; Ansatz-Logging fuer Prompt-Historie.
- **Status:** in progress

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: daily_post_engine + daily_post_topics
- **Datei(en):** alphacycle-x-bot/daily_post_engine.py, alphacycle-x-bot/database.py (`daily_post_topics`, `get_daily_post_topics_last_7_days`, `record_daily_post_topic`), alphacycle-x-bot/config.py (`ALPHACYCLE_PUBLIC_BASE`, `DAILY_POST_DASHBOARD_URL`), alphacycle-x-bot/growth_engine.py (`_format_arc_block` Zusatzzeilen), alphacycle-x-bot/requirements.txt (Kommentar optional Playwright/Selenium), `.gitignore` (`alphacycle-x-bot/artifacts/`), .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Taeglicher Post: `fetch_arc_data()` (GET arc-summary auf alphacycle.app-Basis, Preis cycle/btc, optional cycle-anchor + historical-returns fuer return_12m/win_rate), `generate_daily_post` mit `build_post_prompt` + Claude Sonnet, `generate_daily_post_with_image` mit optionalem Playwright- dann Selenium-Screenshot; kein Auto-Post — nach Telegram-Freigabe `record_daily_post_topic` aufrufen.
- **Warum:** Operating-Brain Daily-Post-Pipeline mit Topic-Historie 7 Tage und optionalem Dashboard-Bild.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: post_system.txt Daily Post Prompt
- **Datei(en):** alphacycle-x-bot/prompts/post_system.txt (Master-Systemprompt exakt laut Spec), alphacycle-x-bot/growth_engine.py (`POST_TYPE_BY_WEEKDAY`, `build_post_prompt` mit `{arc_data_block}`/`{post_type}`/`{posted_topics}`), permanent-fixes.mdc
- **Was wurde geaendert:** Post-Prompt mit SHARE LINES, 7 Post-Typen, Regeln; Wochentag-Mapping Mo-So auf contrarian_signal … weekly_recap; alte `POST_TYPE_SPECS`/`{{...}}`-Platzhalter entfernt.
- **Warum:** Operating-Brain Vorgabe fuer Daily Posts; konsistent mit reply_system-Stil.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: reply_system.txt Cycle Intelligence Desk
- **Datei(en):** alphacycle-x-bot/prompts/reply_system.txt (Master-Systemprompt exakt laut Spec), alphacycle-x-bot/growth_engine.py (Platzhalter-Replace, HOOK ACTIVE/INACTIVE 40%), alphacycle-x-bot/reply_engine.py (User-Hinweis SKIP), permanent-fixes.mdc
- **Was wurde geaendert:** Neuer Reply-Systemtext mit IDENTITY, ARC-Komponenten, 5 Ansaetze, Curiosity-Hook-Regeln; growth_engine ohne str.format auf Volltext (Tweet kann `{` enthalten).
- **Warum:** Operating-Brain Vorgabe fuer Claude Replies.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: growth_engine + Prompt-Templates
- **Datei(en):** alphacycle-x-bot/growth_engine.py, alphacycle-x-bot/prompts/reply_system.txt, alphacycle-x-bot/prompts/post_system.txt, alphacycle-x-bot/reply_engine.py, alphacycle-x-bot/database.py (get_recent_reply_texts), .cursor/rules/permanent-fixes.mdc (growth_engine Regeln)
- **Was wurde geaendert:** Zentrale Prompt-Erzeugung: build_reply_prompt (5 Zufalls-Ansaetze, 40% Curiosity Hook, ARC+History+Tweet); build_post_prompt (Wochentag -> Post-Typ, Topics 7d, Share-Lines-Ende); Master-Rules in TXT; reply_engine nutzt growth_engine + letzte 10 Replies aus SQLite; keine API in growth_engine.
- **Warum:** Operating-Brain / Claude-Pipeline: konsistente Brand-Constraints und Variation; daily_post_engine kann build_post_prompt spaeter nutzen.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: test_telegram_post_real.py
- **Datei(en):** alphacycle-x-bot/test_telegram_post_real.py, RUN_24_7.md
- **Was wurde geaendert:** Skript fuer Telegram-POST-Test mit echter Tweet-ID (eigener Tweet); Hinweis REPLY_DELAY.
- **Warum:** SKIP-Test nutzt Fake-ID; POST braucht echte status-ID.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: Telegram SKIP fix (webhook + feedback)
- **Datei(en):** alphacycle-x-bot/telegram_listener.py, database.py (mark_pending_skipped approved), RUN_24_7.md
- **Was wurde geaendert:** Beim Listener-Start deleteWebhook damit getUpdates Callbacks sieht; Toast-Text nach SKIP/POST; Logging callback data; SKIP auch aus status approved; Troubleshooting in RUN_24_7.
- **Warum:** SKIP wirkte ohne Reaktion wenn Webhook aktiv oder Listener aus; Nutzer braucht sichtbares Feedback.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: 30min Scan, Telegram-Test, SSH-PS1
- **Datei(en):** alphacycle-x-bot/config.py (SCAN default 1800s), .env.example, test_telegram_approval.py, ssh-from-windows.ps1, RUN_24_7.md
- **Was wurde geaendert:** Scan-Intervall Standard 30 Min (Credits); test_telegram_approval.py fuer SKIP-Test; PowerShell-Vorlage fuer ssh root@IP mit Passwort.
- **Warum:** Nutzer wollte Telegram testen und API-Reads reduzieren; SSH von Windows ohne Programmier-Hintergrund.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: verify_env Telegram-Hinweis
- **Datei(en):** alphacycle-x-bot/verify_env.py
- **Was wurde geaendert:** Hinweis wenn TELEGRAM_* fehlen; Erinnerung git pull fuer aktuelle verify_env mit Telegram-Zeilen.
- **Warum:** VPS zeigte alte verify_env-Ausgabe ohne TELEGRAM len-Zeilen.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: 24/7 Runbook + systemd
- **Datei(en):** alphacycle-x-bot/RUN_24_7.md, alphacycle-x-bot/systemd/*.service, alphacycle-x-bot/start.sh (Kommentar)
- **Was wurde geaendert:** Dokumentation: Bot laeuft rund um die Uhr mit zwei Prozessen; X-Replies nur nach Telegram-POST; systemd-Unit-Vorlagen mit WorkingDirectory; screen-Alternative.
- **Warum:** Klare Betriebsanleitung ohne automatische X-Posts ohne Nutzer-Bestätigung.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: Telegram-Genehmigung + pending_replies
- **Datei(en):** alphacycle-x-bot/config.py, database.py, poster.py, bot.py, telegram_bot.py, telegram_listener.py, .env.example, start.sh, start-listener.sh, verify_env.py
- **Was wurde geaendert:** Replies nicht mehr auto-posten; SQLite-Tabelle `pending_replies` (pending/approved/skipped/posted); `sendMessage` mit Inline-Buttons POST/SKIP; `telegram_listener.py` pollt `getUpdates`; `poster.post_reply(tweet_id)` laed Text aus DB; Limits 5/h und 20/Tag in config + Enforcement in poster; Logging fuer Telegram und Post.
- **Warum:** Manuelle Freigabe vor jedem X-Reply; zwei Prozesse: `python3 bot.py` und `python3 telegram_listener.py` (z. B. zwei screen-Sessions).
- **Status:** in progress

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: WClemente als Snowflake-ID
- **Datei(en):** alphacycle-x-bot/config.py
- **Was wurde geaendert:** Erster Eintrag in TRACKED_ACCOUNTS ist `id:1270906326823186432` (verifiziert via resolve_user.py fuer Username WClemente); WClementeIII bleibt ungueltig.
- **Warum:** Username-Lookup kann bei Renames brechen; stabile User-ID vermeidet not-found nach zukuenftigen Aenderungen am @-Handle.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: WClemente handle + resolve_user.py
- **Datei(en):** alphacycle-x-bot/config.py, alphacycle-x-bot/resolve_user.py
- **Was wurde geaendert:** Will Clemente als `WClemente` (statt falscher id/fester wclementeiii); Hilfsskript `resolve_user.py` fuer User-ID per Bearer.
- **Warum:** Falsche Snowflake-ID liefert not-found; aktueller Handle oft WClemente.
- **Status:** in progress

## Letzter Session-Status (2026-04-11) — alphacycle-x-bot: Scanner id: user_id fallback
- **Datei(en):** alphacycle-x-bot/scanner.py, alphacycle-x-bot/config.py
- **Was wurde geaendert:** `TRACKED_ACCOUNTS` Eintraege koennen `id:SNOWFLAKE_ID` sein; Lookup per GET /2/users/:id wenn Username resource-not-found; `author` aus API-Username.
- **Warum:** wclementeiii/WClementeIII liefert bei X v2 teils keinen Username-Match.
- **Status:** in progress

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: TRACKED Fix + 401 Response + MIN_LIKES
- **Datei(en):** alphacycle-x-bot/config.py, post_test_tweet.py, verify_env.py, .env.example
- **Was wurde geaendert:** TRACKED wieder API-tauglich (wclementeiii, CryptoCapo_, DylanLeClair); `MIN_LIKES_TO_REPLY` per Env; `post_test_tweet` druckt 401-Body; `verify_env` mit UTC-Zeit und NTP-Hinweis (`timedatectl`).
- **Warum:** X meldet resource-not-found fuer alte Handles; 401 mit plausiblen Laengen braucht Portal-Token-Reset bzw. Zeit-Sync.
- **Status:** in progress

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Scanner nur Bearer + verify_env
- **Datei(en):** alphacycle-x-bot/scanner.py, alphacycle-x-bot/config.py (TRACKED zurueck), alphacycle-x-bot/verify_env.py
- **Was wurde geaendert:** Scanner-Client nur noch `bearer_token` (Lese-API); OAuth1 dort entfernt; Tracking-Liste wieder wie vom Nutzer; `verify_env.py` fuer Laengen/Newline-Check bei 401 trotz dotenv.
- **Warum:** OAuth1 mit ungueltigen Keys im gleichen Client kann Lookups stoeren; 401 mit len>0 oft abgeschnittene .env-Zeilen oder falsche Secrets.
- **Status:** in progress

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: Handles + .env UTF-8-BOM
- **Datei(en):** alphacycle-x-bot/config.py, alphacycle-x-bot/post_test_tweet.py
- **Was wurde geaendert:** `TRACKED_ACCOUNTS`: capaboreal -> CryptoCapo_, DylanLeClair_ -> DylanLeClair, WClemente -> wclementeiii; `load_dotenv(..., encoding=utf-8-sig)` gegen BOM; `ENV_FILE` fuer Diagnose; post_test_tweet zeigt .env-Pfad wenn Keys fehlen.
- **Warum:** X API resource-not-found fuer falsche Handles; 401 moeglich durch BOM/erste Zeile in .env.
- **Status:** in progress

## Letzter Session-Status (2026-04-10) — alphacycle-x-bot: load_dotenv override + Scanner-Fehler
- **Datei(en):** alphacycle-x-bot/config.py, alphacycle-x-bot/scanner.py
- **Was wurde geaendert:** `load_dotenv(..., override=True)` damit `.env` leere Shell-Exports ueberschreibt (sonst 401 trotz gueltiger .env); Scanner loggt API-`errors` bei User-Lookup.
- **Warum:** VPS-Sessions mit exportierten aber leeren TWITTER_* blockieren dotenv; klarere Diagnose bei "User not found".
- **Status:** in progress

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: dotenv, Start-Skript, Test-Post
- **Datei(en):** alphacycle-x-bot/config.py, requirements.txt, bot.py (--once), poster.py (403-Hinweis), post_test_tweet.py, start.sh, .env.example
- **Was wurde geaendert:** `python-dotenv` laedt `.env` automatisch aus dem Ordner von `config.py`; `DB_PATH` absolut dorthin; `SCAN_INTERVAL_SECONDS` default 300 per Env override; `bot.py --once` fuer einen Zyklus; `post_test_tweet.py` fuer Standalone-Write-Test; `start.sh` fuer VPS/screen ohne manuelles `source .env`; klarere 403-Logs beim Reply.
- **Warum:** Bot soll ohne Shell-`export` laufen; schneller Testzyklus und einfacher Write-Test.
- **Status:** in progress (VPS: `git pull`, `pip3 install -r requirements.txt`, `chmod +x start.sh`)

## Letzter Session-Status (2026-04-09) — alphacycle-x-bot: Twitter/X 401 Posting-Diagnose
- **Datei(en):** alphacycle-x-bot/config.py, alphacycle-x-bot/poster.py, alphacycle-x-bot/test_manual_reply.py, .cursor/rules/permanent-fixes.mdc
- **Was wurde geaendert:** Alle Twitter/Claude-Env-Werte mit `.strip()`; poster: explizit `user_auth=True`, klare Prüfung OAuth-User-Credentials, `tweepy.Unauthorized` mit Response-Body + Hinweis (Bearer vs OAuth1, Screen-Env, Token-Regeneration); `test_manual_reply.py` für manuellen `get_me` + Reply-Test.
- **Warum:** 401 beim Posten tritt häufig auf, wenn nur der Bearer für Reads gesetzt ist oder OAuth-Secrets whitespace-/App-mismatch haben; Scan kann unabhängig davon funktionieren.
- **Status:** in progress (VPS: Env prüfen, ggf. Tokens nach Read+Write neu generieren)

## Letzter Session-Status (2026-04-08) — Hotfix: Hero Orbit Mobile (CSS-only)
- **Datei(en):** index.html
- **Was wurde geaendert:** Einheitlicher `@media (max-width: 700px)`-Block im HERO ORBITAL-Abschnitt: Ring 180px, Score 42px, kleinere gauge-denom/score-phase/#hero-regime-context, Orbit-Labels weiter aussen (ol-*), Components-Stack, Hero-Padding reduziert; globale Zone-Leiste unter `#btc-card.hero-card .hero-zones` (opacity 0.6, hz-range/hz-label Lesbarkeit); `@media (max-width: 400px)` Ring 160px / Score 36px. Entfernt: spaetere Overrides in `@media (max-width: 480px)` und `@media (max-width: 360px)` fuer `#btc-card` gauge/components sowie das alte `@media(max-width:700px)` nur fuer `.components-grid` (Konflikt mit Orbit-Flex).
- **Warum:** Ueberlappungen auf Mobile; widerspruechliche spaete CSS-Regeln haben Orbit-Fixes ueberschrieben.
- **Status:** deployed

## Letzter Session-Status (2026-03-18) — Style: Hero Refinement V2 (CSS-only)
- **Datei(en):** index.html
- **Was wurde geändert:** Nur CSS-Overrides fuer `#btc-card.hero-card` (Score dominanter, Card wieder contained mit Border/Shadow, reduced noise); kein HTML/JS/IDs angefasst.
- **Warum:** Safe UX-Polish ohne Risiko fuer Logik/Layouts (CSS-only).
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — Style: Hero Refinement V4 (CSS-only)
- **Datei(en):** index.html
- **Was wurde geändert:** CSS-Polish fuer Hero (gauge-val groesser, Gauge-SVG leicht gedimmt, Components-Bereich und Factor-Values gedimmt); keine Layout/HTML/JS-Aenderungen.
- **Warum:** Visuelle Beruhigung (weniger Noise), Score dominiert weiterhin.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — Hero Orbital Instrument (re-implementation; ::before mask fix)
- **Datei(en):** index.html
- **Was wurde geändert:** Orbit-Ring um `gauge-wrap` wieder integriert (`orbit-ring`/`orbit-dot` + `orbit-inner-ring`/`orbit-ticks` + 5 Orbit-Zonenlabels). Gradient-Ring rendert über `.orbit-ring::before` mit eigener Mask (Container bleibt transparent), Dot-Position via `positionOrbitDot()` und Zone-Highlight via `highlightOrbitZone()`. Resize-Sync + PNG-Export Safety (temporär `btc-card` Hintergrund `#0a1228`).
- **Warum:** Orbit ist wieder sichtbar und Overlay/Mask blendet Score/Dot nicht aus.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — Hotfix: Orbit Labels + Ring Visibility
- **Datei(en):** index.html
- **Was wurde geändert:** Orbit-Labels nach außen verschoben (ueber `ol-*` top/left so dass sie nicht den Score ueberlappen), `.orbit-ring` `overflow: visible` gesetzt, Gradient-Ring heller (`.orbit-ring::before` opacity auf `1`), innerer Ring heller (`border`/`opacity` von `0.05/0.6` auf `0.08/0.8`), Mobile Label-Offsets final justiert.
- **Warum:** Orbit war optisch zu dunkel bzw. Labels ueberschneiden den Score; jetzt klare Sichtbarkeit und Instrument-Lesbarkeit.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — HERO ORBIT PREMIUM — Match reference design (CSS only)
- **Datei(en):** index.html
- **Was wurde geändert:** Orbit Premium Visuals im Hero: Ring-Dicke/Mask (90/91), kompletter Ring-Glow-Aura, dunkler Innenbereich hinter Score via `.orbit-inner-ring` radial gradient + `z-index: -1`, Dot (14px) + stärkerer Glow/Trail, Orbit-Labels größer (9px) und außerhalb positioniert, `.orbit-label.active` stärkerer Glow, `ARC RISK` im Hero per CSS ausgeblendet (first `.gauge-denom` in `.gauge-center`), Score-Glow und `#hero-regime-context` feinjustiert, Mobile Label-Offsets entsprechend angepasst.
- **Warum:** Match reference design; bessere Lesbarkeit (Score/Dot) und klarer Orbit-„Instrument“-Look ohne HTML/JS-Änderungen.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — hotfix: Orbit Labels weiter außen + Context kürzer
- **Datei(en):** index.html
- **Was wurde geändert:** `.ol-*` Positionen im Hero-Orbit (Desktop + Mobile) weiter nach außen geschoben (overflow: visible bleibt aktiv). `#hero-regime-context` kompakter (max-width 200px, font-size 9px), damit es weniger Platz einnimmt.
- **Warum:** Labels sollen sichtbar außerhalb des Rings sitzen (kein Überlappen/Verdecken) und Context-Text soll die Hero-Fläche weniger dominieren.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — fix: HERO ORBIT match reference (6 fixes)
- **Datei(en):** index.html
- **Was wurde geändert:** `orbit-ring::before` per !important gegen Override/Masking sichtbar gemacht; `ol-*` Offsets (Desktop + Mobile) auf Referenzwerte verschoben; `ARC RISK` im Hero per CSS ausgeblendet; `_getCycleDescription()` exakt nach Referenz-Textstrings ersetzt; Dot-Glow und Score-Glow verstärkt.
- **Warum:** Gradient-Ring war zu dunkel/unsichtbar, Labels deckten Score eher ab, ARC RISK lenkte ab, und Glows waren im Vergleich zur Referenz zu schwach.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — refactor: Historical Returns — YOU ARE HERE focus block
- **Datei(en):** index.html
- **Was wurde geändert:** Single dominanter `hr-focus` Block (YOU ARE HERE) ergänzt; bestehende `.hr-grid` nur per `display:none !important` ausgeblendet; `updateHRFocus()`/`updateHRContext()` ergänzt und am Ende von `fetchHistoricalReturns()`/`applyHistoricalReturnsCurrentZone()` aufgerufen.
- **Warum:** Radikaler Fokus auf die aktuelle Zone (eine große Zahl + Kontextzeile), weniger visuelles Rauschen.
- **Status:** ✅ deployed

## Letzter Session-Status (2026-03-18) — Rollback: UX Prompts vom 2026-03-17 (Decision/Positioning)
- **Rollback:** Fehlgeschlagene UX-Iteration von gestern (Positioning Framework / Decision-Layout / Live-Prices-Reihenfolge) zurückgerollt.
- **Betroffen:** `index.html` (UI), `DEPLOY_STATE.md` (Dokumentation), `.cursor/rules/permanent-fixes.mdc` (nur Doku-Zeile).
- **Warum:** UI-Änderungen waren instabil bzw. führten zu fehlerhaften/unerwünschten UX-States im IDE-Test.
- **Status:** ✅ deployed (Commit-Reverts, kein Force-Push)

## Letzter Session-Status (2026-03-17) — Precision Polish: Zone History Scanability + Weekly→Daily Wording
- **Zone History:** Expansion-Zeilen erhalten Klasse .zone-row-expansion (opacity 0.5, hover 0.8), damit BUY ZONE / NO ENTRY / SELL-REDUCE-Zeilen visuell dominieren. Keine Zeilen ausgeblendet, nur Opacity.
- **Disclaimer:** HR-Disclaimer und Landing/Track-Record-Text von „weekly backtest data“ auf „daily backtest data“ geändert. JS-Variablen (btcWeekly, ethWeekly, const weekly, etc.) unverändert (intern).

## Letzter Session-Status (2026-03-17) — How ARC Works: Soft-Gated Methodology
- **Methodology-Block:** #arc-method-content in zwei Stufen geteilt: #arc-method-free (nur 4 Komponentennamen + kurzer Kontext + CTA) und #arc-method-paid (Gewichte-Balken 35/25/25/15 + detaillierte Beschreibungen). Anzeige nach currentPlan: paid/trial sehen paid, free/anonymous sehen free.
- **updateArcMethodologyGate():** Zeigt free- oder paid-Inhalt, setzt CTA für free („UPGRADE TO SEE FULL METHODOLOGY →“ / openUpgradeModal) bzw. anonymous („UNLOCK FULL METHODOLOGY →“ / openAuthModal('signup')). Wird am Ende von applyBlurGates() aufgerufen.
- **Toggle:** toggleArcMethodology() unverändert; bei geöffnetem Block wird maxHeight nach Gate-Update neu berechnet. Mobile: #arc-method-free Grid bleibt 2 Spalten (480px). Keine Änderung an applyBlurGates/gateInfo, Auth oder Backend.

## Letzter Session-Status (2026-03-17) — Zone History: Zone-Aware Signal Labels
- **Zone History Tabelle:** Spalte „Entry“ in „Signal“ umbenannt. Anzeige-Logik in renderZoneHistory() zonenbasiert: Deep Value → „↑ BUY ZONE“ (grün); Accumulation → „↑ BUY ZONE“ (grün) bzw. „↓ BUY ZONE“ (cyan #00B4D8); Expansion → „↑ Uptrend“ / „↓ Downtrend“ (gedimmt); Risk Rising → „⚠ NO ENTRY“ (orange); Euphoria → „⚠ SELL / REDUCE“ (rot). Backend direction und API-Response unverändert; nur Frontend-Darstellung.

## Letzter Session-Status (2026-03-17) — Hotfix: Track Record Deep Value Return
- **Track Record Highlights:** Deep-Value-12M-Return in #track-dv-return auf +260% aktualisiert (Quelle /api/historical-returns deep_value.avg_12m, verified 2026-03-17). Nur dieser Wert und Verifizierungs-Kommentar geändert.

## Letzter Session-Status (2026-03-17) — Decision Engine: Move to position 5 + ARC chart auto-fit price axis
- **DOM-Reihenfolge:** `gate-decision-engine` nach `gate-historical-returns` eingefügt (vor `gate-cycle-overview`), und „DEEP ANALYSIS“-Separator bleibt vor `gate-arc-history` korrekt positioniert (Signal-Hierarchie: Score → Signal Summary → HR → Decision → Cycle → Deep Dive).
- **ARC Chart:** `autoFitPriceAxis()` hinzugefügt (Re-entrancy Guard), passt yPrice (BTC) min/max beim Zoom/Pan auf den sichtbaren X-Bereich an; yArc bleibt 0–100 fix.
- **Reset/Doppelklick:** `resetArcZoom()` und Double-Click stellen die originale yPrice (Full-Range) Bounding-Werte wieder her.
- **Zoom/Pan Callbacks:** onZoom/onPan in der Chart.js zoom/pan Konfiguration ruft `autoFitPriceAxis()` auf.

## Letzter Session-Status (2026-03-17) — Decision Engine: 3-Layer Interpretation Framework
- **Neue Interpretation-Layer:** Unterhalb des bestehenden Decision-Grids (Position/Allocation/Range/Confidence) wird ein dreiteiliger Interpretationsbereich gerendert: Regime Interpretation, Typical Positioning und Risk/Reward Profile.
- **JS-Rendering:** Neue Funktion `renderDecisionInterpretation(score)` füllt zone-spezifische Inhalte anhand des ARC Score und wird am Ende von `renderDecision()` mit derselben Score-Quelle aufgerufen.
- **Blur-Gate:** Der Layer liegt innerhalb von `gate-decision-engine` und wird vom bestehenden Blur-Gate abgedeckt, wenn gelockt.

## Letzter Session-Status (2026-03-17) — Snapshot Bugfix: days_since_top parameter
- **build_snapshot():** Signatur um `days_since_top` ergänzt, damit der Parameter aus `/api/snapshot` ohne TypeError akzeptiert wird.
- **Snapshot Dict:** `days_since_top` wird im Snapshot-Dict bereitgestellt (nur bei vorhandenem Value).

## Letzter Session-Status (2026-03-18) — UI/UX Finalization: Signal Summary + HR/Chart/Cycle/Landing
- **Signal Summary:** Auf „[ZONE] PHASE · ARC [SCORE]“ reduziert; Kontext/Allocation ausgeblendet.
- **HR Grid:** `hr-current-zone` visuell stärker hervorgehoben und DV/EU mit subtilen linken Border-Akzenten ergänzt.
- **ARC Chart:** Kleines `currentPriceLabel` Plugin ergänzt (rechte Kante, 8px, niedrig kontrast).
- **Cycle Overview:** Vorhersage-Elemente (`ca-window`, `ca-confidence`) ausgeblendet + Regime-Kontext-Subtext ergänzt.
- **Landing:** Action-basierte Now-Teaser/Return-Claim entfernt; jetzt deskriptive Regime-Formulierungen ohne hardcoded Prozent.

## Letzter Session-Status (2026-03-18) — UI Refinement: Hero instrument mode + visual calming
- **Hero:** Card-Container (background/border/glow) entfernt, Score als floating instrument zentriert und dominant skaliert.
- **Hero Context:** 1-line regime interpretation unterhalb der Zone-Label ergänzt (`hero-regime-context`).
- **Hero Metadata:** BTC/ETH/MACRO subscores sowie Momentum/Percentile in der Hero reduziert/ausgeblendet; BTC price als `BTC/USD · Kraken · $X` dim angezeigt.
- **HR Grid:** Rückkehrwerte und Supporting-Text visuell verkleinert/dimmed (Return/Wr/Count/Label).
- **Positioning Framework + Spacing:** Decision-Card visuell beruhigt und Section-Abstände reduziert Konflikte / mehr breathing room.

## Letzter Session-Status (2026-03-18) — Hotfix: Live Prices nach Historical Returns
- **DOM:** `gate-live-prices` nach `gate-historical-returns` verschoben (vor `gate-decision-engine`).
- **CSS:** Preise-Grid kompakt (3 Spalten Desktop) inklusive reduzierte Card-Paddings/Typo.
## Letzter Session-Status (2026-03-11) — Trust Layer Phase T-C: Track Record Highlights + Footer Sources Cleanup
- **Track Record Highlights:** Kompakter Block `.track-highlights` nach gate-content-export, vor DATA SOURCES. Vier hardcodierte Stats: 10/10 Major cycle tops & bottoms, verifizierter Deep-Value-12M-Return (+X%), 8 Jahre ARC-Daten seit Aug 2017, 4 Quellen (Kraken · Alternative.me · DeFiLlama · FRED). Link „VIEW FULL TRACK RECORD →“ ruft showTrackRecord() auf. Kein Blur-Gate, immer sichtbar.
- **CSS:** .track-highlights-grid 4 Spalten, Border/Track-Style; .track-stat, .track-stat-value, .track-stat-label. @media 600px: 2 Spalten; @media 380px: 1 Spalte, kleinere Padding/Schrift.
- **Footer Data Sources:** .status-row auf 4 sichtbare Pills + Timestamp konsolidiert: Kraken, Fear & Greed, DeFiLlama, FRED, src-ts (src-ts-lbl). DeFiLlama Stablecoins als eigenständige Pill entfernt; Element #src-stable bleibt im DOM mit display:none, damit markSources() weiterhin gesetzt werden kann.
- **Unverändert:** markSources()-Logik, showTrackRecord(), Blur-Gates, Section-Reihenfolge, ARC-Formel, Backend, Track-Record-Seite als eigene View. Keine neuen Endpoints, keine dynamischen Berechnungen.

## Letzter Session-Status (2026-03-11) — Trust Layer Phase T-B: Live vs History Labels + Chart Start Annotation
- **BACKTEST-Badges:** .sec-badge „BACKTEST“ bei Historical ARC Returns, ARC History und Zone History (zwischen sec-title und sec-line). .module-tertiary .sec-badge: 7px, padding 1px 5px, opacity 0.6; .module-secondary .sec-badge: 8px.
- **Chart-Start-Tooltip:** Neben #arc-chart-title ein .chart-info-tip (ⓘ) mit tabindex="0"; Hover/Focus zeigt .chart-info-tooltip (Warum ARC ab Aug 2017: 200-Wochen-MA braucht 1.400 Tage Vorlauf, BTC-Preise ab Okt 2013 Kraken). Mobile: Tooltip 220px, right:-10px, 8px Schrift.
- **LIVE-Indikatoren verifiziert:** #hero-freshness (Phase E) und #dec-live-tag (renderDecision) vorhanden und funktionsfähig. Keine Formel-, Zonen- oder Backend-Änderungen.

## Letzter Session-Status (2026-03-11) — Trust Layer Phase T-A: Component Source Labels + How ARC Works
- **Quellen-Labels:** In jeder der 4 .factor-card (200W MA DEV, DRAWDOWN, FEAR & GREED, LIQUIDITY) ein .factor-source unter dem factor-value: Kraken BTC/USD, Kraken BTC/USD, Alternative.me, FRED (Fed Net Liquidity). CSS: 7px, var(--tx-ter), opacity 0.6, margin-top 2px. Sichtbar nur wenn Komponenten ausgeklappt (Phase A).
- **How ARC Works:** Expandierbarer Block #arc-methodology nach hero-components-collapse, vor .hero-zones (innerhalb gate-hero blur-content). Toggle-Button „HOW ARC WORKS“, Klick ruft toggleArcMethodology(); Inhalt: Einleitung, Gewichte-Balken (35/25/25/15), .arc-weights-grid mit 4 Komponenten-Beschreibungen (Trend, Drawdown, Liquidity, Sentiment), Abschlusszeile. Standard eingeklappt (max-height:0). Keine Formel- oder Backend-Änderung.
- **Mobile:** @media (max-width:480px) .arc-weights-grid: grid-template-columns: 1fr !important. Phase A–E, Blur-Gate, alle IDs unverändert.

## Letzter Session-Status (2026-03-11) — ARC Chart: 10Y Default Zoom to Last 2 Years
- **10Y Chart:** Nach Erstellung wird die x-Achse programmatisch auf die letzten ~730 Datenpunkte (~2 Jahre) gezoomt. Nutzer sieht zuerst die jüngste Geschichte; Pan links / Zoom out zeigt den vollen 10Y-Bereich.
- **RESET-Button:** Führt `resetArcZoom()` aus: bei 10Y Rückkehr zur 2Y-Default-Ansicht (nicht Vollbereich); bei 1Y wie bisher `resetZoom()`. Button-Title: „Reset to 2Y view (double-click chart for full range)“.
- **Doppelklick auf Canvas:** Unverändert `chart.resetZoom()` → voller 10Y-Bereich (Escape-Hatch).
- **1Y-Chart:** Unverändert, kein Default-Zoom. `window._arcPeriod` und `window._arcDefaultZoom` werden in `renderArcChart()` gesetzt; Zoom-Plugin-Config, Datasets, priceMin/priceMax, Formel und Backend unverändert.

## Letzter Session-Status (2026-03-11) — Premium UI Phase E: Micro-Polish
- **Fade-in:** .anim nutzt weiterhin fadeUp (opacity + translateY); @media (prefers-reduced-motion: reduce) setzt animation: none und opacity: 1 für .anim. Keine strukturellen Änderungen.
- **Hero Freshness:** #hero-freshness im Hero-Header; updateHeroFreshness() zeigt LIVE / Xm ago / Xh ago; S._lastRefresh wird in updateUI() bei „Last updated“ gesetzt; 60s-Interval für Aktualisierung. Kein neues Backend.
- **Loading-States:** .is-placeholder (color: var(--tx-ter)) für Werte „—“; setText() und updateGauge() setzen/entfernen die Klasse; showSkeletons() setzt Em-Dash und is-placeholder. .loading-text (dim + italic) für „Loading…“ / „Historical zone statistics loading…“; zone-history-sub initial mit loading-text, Entfernung in renderZoneHistory bei echten Daten; signal-summary-context bei Loading-Text mit loading-text.
- **Quellen-Badges:** HR-Eyebrow um „· Kraken BTC/USD“ ergänzt; ARC-Chart-Subtitle (1Y) um „· Kraken BTC/USD“ ergänzt (10Y war bereits vorhanden); Zone-History-Titel um „· Daily ARC data since 2017“ ergänzt.
- **Smooth Scroll:** .zone-history-table-wrap und .hr-grid mit scroll-behavior: smooth; bei prefers-reduced-motion: reduce auf html und diese Container scroll-behavior: auto. Keine Layout- oder Formel-Änderungen.

## Letzter Session-Status (2026-03-11) — Premium UI Phase D: Mobile Narrative Flow
- **Mobile (≤600px):** Tertiär-Sektionen (Cycle Overview, Near-Term, ARC History, Momentum, Zone History, Content Export) starten eingeklappt; nur sec-header + Pfeil sichtbar, Tap auf Header klappt Inhalt auf/zu (Klasse `mobile-expanded`). initMobileCollapseToggle() nach initAuth() und bei Resize (bei >600px werden alle mobile-expanded entfernt). gate-arc-momentum hat sec-header nachgerüstet für einheitliches Verhalten.
- **ARC Chart:** Beim Aufklappen von gate-arc-history wird nach 500ms window._arcHistoryChart.resize() aufgerufen. Duplicate-Binding verhindert durch _mobileToggleBound-Flag.
- **Live Prices:** Auf Mobile kompakter: prices-grid 1fr, gap 6px, price-card padding 8px 12px, sparkline 24px, pc-stat 9px.
- **Historical Returns:** hr-grid auf Mobile mit scroll-snap-type: x mandatory, hr-zone flex 0 0 160px, scroll-snap-align: start.
- **Zone History:** zone-history-table-wrap max-height 250px, Tabellen-Zellen padding 4px 6px, font-size 9px.
- **Desktop:** Alle Änderungen nur in @media (max-width: 600px); Desktop-Layout unverändert. Keine Änderungen an ARC-Formel, Zonen, Backend, Blur-Gates oder Chart.js-Config.

## Letzter Session-Status (2026-03-13) — ARC Chart: Legend Cleanup + 1Y Price Axis Fix
- **Legend Cleanup:** Chart.js Legend-Filter in renderArcChart() zeigt nur noch zwei Einträge: „ARC Index“ und „BTC Price“. Alle Zonen-Datasets, High/Low-Range und Live bleiben in datasets erhalten, werden aber aus der Legende gefiltert (Zonen weiter über farbige Bänder + Labels sichtbar).
- **1Y Price Axis Fix:** yPrice-Skala (logarithmisch) erhält `ticks.maxTicksLimit = (period === '1y' ? 6 : 10)`, so dass auf 1Y maximal ca. 6 Preislabels angezeigt werden und Überlappungen auf engen Preisbereichen vermieden werden. 10Y behält bis zu 10 Ticks für das volle Log-Intervall. Keine Änderung der x-Achse, yArc, priceMin/priceMax oder Zoom/Pan.

## Letzter Session-Status (2026-03-13) — Premium UI Phase C: Color Restraint
- **Historical Returns:** Zonenfarben nur noch als Akzent: Range-Labels (0–29, 30–39 etc.) bleiben farbig, Returns (`hr-zone-return`) werden neutral (rgba(255,255,255,0.85)); jede Zone erhält eine linke Border in Zonenfarbe (Deep Value/Accumulation/Expansion/Risk Rising/Euphoria). Aktuelle Zone („YOU ARE HERE“) behält ihren Highlight-Border.
- **Zone History:** Return-Spalte `.zone-history-return-pos/neg` auf weichere Grün/Rot-Töne (70% Opazität) reduziert; Zonenspalte bleibt vollfarbig zur Kennzeichnung.
- **Hero:** Zone-Bar Range-Zahlen (`.hz-range`) auf 70%-Opazität der jeweiligen Zonenfarbe reduziert; Hero-Subscores (`hs-val`) und Meta-Werte (`hm-val`) werden via CSS `!important` neutral auf `var(--tx-sec)` gesetzt, so dass nur Score-Zahl und Phasenname volle Zonenfarbe tragen.
- **Decision Engine:** Sekundäre Werte `#dec-allocation` und `#dec-confidence` neutralisiert (tx-sec, `!important`); Position (`#dec-position`) und Range (`#dec-range`, inkl. Risiko-Rot) bleiben durch JS eingefärbt.
- **Zone Accent Variable:** In `updateUI()` wird nach Ermittlung von `bCol=scoreColor(combinedScore)` eine dynamische CSS-Variable `--zone-accent` (und dim-Variante `--zone-accent-dim`) auf `:root` gesetzt. Aktuell nur Vorbereitung für spätere Phasen, ohne sichtbare Änderung.

## Letzter Session-Status (2026-03-13) — Mobile CSS Bug Fixes (Chart Header, Titles, Decision Padding)
- **ARC Chart Header (≤480px):** Header-Row in `#arc-chart-card` wrappt jetzt per `flex-wrap: wrap` und reduziertem `gap`; Buttons EXPORT/SHARE werden auf sehr kleinen Screens per CSS (`display:none`) ausgeblendet, RESET wird verkleinert (8px, 3x6px). Auf Desktop bleiben alle Buttons und Layout unverändert.
- **Title-Hierarchie mobil:** Die pauschale `.sec-title { font-size: 11px !important; }`-Regel im ≤480px-Block wurde durch eine Basisregel ohne `!important` plus spezifische Overrides ersetzt: `.module-secondary .sec-title 10px !important`, `.module-tertiary .sec-title 8px !important`. Phase-B-Hierarchie (drei Titelgrößen) bleibt damit auch auf Mobile sichtbar.
- **Decision Engine Padding (≤700px):** Zwischen 481–700px reduziert `@media(max-width:700px)` das Padding der `.decision-item`-Cards auf 1rem x 1rem und verkleinert `.decision-value` auf 1.2rem mit `word-break: break-word`, damit der 2x2-Grid lesbar bleibt, ohne Desktop-Darstellung zu verändern.

## Letzter Session-Status (2026-03-13) — Premium UI Phase B: Visual Weight System + Spacing
- **3-Stufen-Hierarchie:** module-secondary (Decision Engine, Historical Returns): hellere Karte (rgba 0.025), Border 0.07, border-radius 12px, sec-title 11px, sec-line dezenter. module-tertiary (Cycle Overview, Near-Term, ARC History, Momentum, Zone History, Content Export): kompakter (rgba 0.015), Border 0.04, border-radius 10px, card-accent ausgeblendet, sec-title 9px.
- **Spacing-Variablen:** --space-section-primary 32px, --space-section-secondary 24px, --space-section-tertiary 14px, --space-group-break 40px. #gate-historical-returns margin-top group-break; #gate-cycle-overview margin-top group-break. .module-tertiary + .module-tertiary margin-top tertiary; .module-secondary + .module-secondary margin-top secondary.
- **Trennlinien:** Separator-Divs (HISTORICAL CONTEXT, DEEP ANALYSIS) margin:0; vertikaler Rhythmus nur ueber Weight-System.
- **Mobile @600px:** Spacing-Variablen reduziert (24/18/10/28px), sec-title secondary 10px, tertiary 8px. Hero (Phase A) unveraendert. Keine Backend-, ARC- oder Blur-Gate-Logik-Aenderungen.

## Letzter Session-Status (2026-03-13) — Premium UI Phase A: Hero Redesign + Score Dominance
- **Hero Card:** ARC-Score ist dominantes Element: gauge-val clamp(48px, 8vw, 72px), score-phase clamp(14px, 2vw, 18px), gauge-wrap max-width 180px. Hintergrund rgba(10,18,40,0.5), Border 1px solid rgba(255,255,255,0.06), kein Gradient/Glow; card-accent und card-glow-btc (box-shadow, ::before, ::after) fuer Hero ausgeblendet.
- **Komponenten-Gauges:** Standardmaessig eingeklappt; Wrapper #hero-components-collapse mit max-height:0; Toggle-Button "SHOW COMPONENTS" / "HIDE COMPONENTS" mit toggleHeroComponents(); IDs btc-components, gauge-ma/dd/fg/liq, val-* unveraendert.
- **Zonenleiste:** Zurueckhaltend: margin-top 12px, padding-top 8px, opacity 0.6, hz-range 10px, hz-label 7px, hero-zone padding 6px 12px.
- **Abstand:** #gate-hero margin-bottom 32px.
- **SHARE PNG:** Button per style="display:none" versteckt; nur bei ?admin=ac_internal_2026 in boot() auf inline-block gesetzt.
- **Mobile:** @media (max-width:700px) Hero padding 1.5rem 1rem, margin 0 -10px, border-radius 0, gauge-wrap 160px/120px, gauge-val clamp(44px,12vw,64px), score-footer/hero-subscores/hero-meta-row zentriert; @media (max-width:480px) gauge-val clamp(40px,14vw,56px), score-phase 13px. Keine ARC-Formel-, Backend- oder Blur-Gate-Struktur-Aenderungen.

## Letzter Session-Status (2026-03-13) — ARC Daily Migration: Static CSV Integration
- **CSV-basierte Daily-Historie:** Statische Datei `backend/data/btc_daily_kraken.csv` (Kraken BTC/USD Daily OHLC, Format: timestamp,open,high,low,close,volume,trades). Sollte 3727 Zeilen (2013-10-06 bis 2023-12-31) enthalten. Bei weniger Zeilen: Platzhalter mit `python backend/scripts/gen_btc_csv.py` erzeugen oder offizielle Kraken-CSV ablegen. Wenn CSV fehlt oder leer: Fallback auf woechentlichen Backtest.
- **Drei Quellen in _load_or_build_daily_cache():** (1) CSV als Basis, (2) Luecke zwischen CSV-Ende und Kraken-API-Anfang per CryptoCompare e=Kraken (_fetch_gap_from_cryptocompare, optional CRYPTOCOMPARE_KEY), (3) Kraken Live-API (~720 neueste Tage). Merge, Dedup nach Datum, Sort, Persist in /tmp/daily_full_cache.json. Inkrementelles Update wenn Cache existiert und >2000 Eintraege.
- **_fetch_btc_daily_full() deaktiviert** (Kraken liefert nur ~720 neueste Daily-Candles); Log-Hinweis "use CSV-based cache loader". run_daily_backtest_full() unveraendert, ruft weiter _load_or_build_daily_cache().

## Letzter Session-Status (2026-03-13) — ARC Daily Migration (Unified Daily Backtest)
- **Kraken Daily-Limitierung:** Die oeffentliche Kraken Daily-OHLC-API (interval=1440) liefert nur ca. 720 der **neuesten** Tages-Candles. Vollbereich ab 2013 ueber API nicht moeglich; daher CSV + Gap-Bridge + API (siehe Static CSV Integration).
- **Single source (wenn genug Daily-Daten):** Alle ARC-Historie nutzen `run_daily_backtest_full()` mit taeglichen Candles. MA200w aus Daily-Preisen via [::7]-Slice und moving_average(..., 200), exakt wie compute_btc_score() (scoring.py).
- **backtest_engine.py:** Neue `_fetch_btc_daily_full()` (paginated daily OHLC), `_load_or_build_daily_cache()` (File /tmp/daily_full_cache.json, inkrementelles Update, letzter Eintrag vor Append verworfen), `run_daily_backtest_full()`. Fallback auf `run_backtest()` nur bei zu wenig Daily-Daten (<1400 Punkte) oder Fehler. `run_backtest()` und `run_daily_backtest()` mit Deprecation-Hinweis (temporaerer Rollback).
- **Dual-Validation-Log:** Drei Referenzdaten (2022-11-21, 2024-03-14, 2025-01-20) werden als ARC VALIDATION daily=... weekly=... delta=... geloggt.
- **main.py:** Startup loescht zusaetzlich /tmp/daily_full_cache.json. refresh_cache() ruft run_daily_backtest_full() auf, bei leerem Ergebnis Fallback run_backtest(); CACHE.pop("daily_history") entfernt. /api/backtest und /api/history-daily nutzen run_daily_backtest_full() (Fallback weekly). /api/history-daily liefert last 365 aus CACHE["backtest_results"], Live-Override letzter Punkt unveraendert. /api/historical-returns und /api/arc-forward-returns bei Cache-Miss ebenfalls run_daily_backtest_full() mit Fallback.
- **Frontend:** 10Y-Chart nutzt S.backtest ohne Truncation. 1Y-Chart weiterhin aus dailyHistory (last 365 aus Backend).
- **ARC Chart Pan/Zoom/Reset:** Chart.js 4.x + chartjs-plugin-zoom@2.0.1 + Hammer.js bereits eingebunden. Zoom-Optionen: pan (mode x, modifierKey null), zoom (wheel + pinch, mode x), limits.x.minRange 30 Tage. Reset-Button #reset-zoom-arc-btn ruft _arcHistoryChart.resetZoom() auf. 10Y-Chart zeigt erstes Datum ~2017: Ursache ist Backend (run_daily_backtest_full braucht MIN_DAYS_FOR_MA200W = 1400 Tage vor erstem ARC-Punkt; CSV-Start 2013-10-06 + 1400 Tage). Kein Frontend-Filter.

## Letzter Session-Status (2026-03-13) — Auth/Payment Error States (Phase 1 Prompt 2)
- **Frontend showPlanWarning()**: Leichtes Banner unten (position:fixed; bottom:20px; z-index:9999; amber), auto-dismiss nach 8s; entfernt vorhandenes #plan-warning vor Neu-Anzeige. Wird von fetchUserPlan, openUpgradeModal und ggf. weiteren Auth/Payment-Fehlern genutzt.
- **fetchUserPlan**: 8s Timeout via AbortController/setTimeout; bei Timeout oder Netzwerk-/Parse-Fehler currentPlan = 'free', showPlanWarning('Could not verify your plan. Some features may be temporarily hidden.'); bei data.error === 'profile_fetch_failed' dieselbe Meldung. applyBlurGates() weiterhin am Ende (auch im catch) aufgerufen.
- **openUpgradeModal**: Kein alert() mehr. Bei !resp.ok: 401 → showPlanWarning + openAuthModal('login'); 503 → Payment temporarily unavailable; sonst Checkout failed. Im catch (Netzwerk etc.) showPlanWarning('Checkout temporarily unavailable. Please try again in a moment.'). Buttons in allen Fehlerpfaden zurueckgesetzt (REDIRECTING... → UPGRADE TO PRO).
- **handleAuthSubmit**: Sign-Up-Erfolg nur noch closeAuthModal() (Confirm Email ist in Supabase aus; kein "Check your email"-Text). Bei Fehler: wenn result.error.message "already registered" oder "already exists" enthaelt → Anzeige "This email is already registered. Try logging in instead."
- **GET /api/auth/profile**: Profil-Abfrage (supabase.table user_profiles select/single/execute) und Insert (neues Profil) in try/except. Bei Exception: logger.error, Rueckgabe {"authenticated": true, "plan": "free", "email": user.email, "subscription_status": "unknown" bzw. "inactive", "error": "profile_fetch_failed"}. Frontend kann data.error nutzen fuer showPlanWarning.
- **POST /api/checkout**: Unveraendert; liefert bei fehlenden Stripe-Keys 503 mit detail, bei Stripe-Fehler 500 mit detail (JSON parsebar).

## Letzter Session-Status (2026-03-13) — Stripe Entitlement Hardening (Phase 1)
- **Webhook:** State-based duplicate protection: vor jedem Update wird aktuelles Profil geladen; bei checkout.session.completed Skip wenn plan bereits paid; bei subscription.updated Skip wenn subscription_status bereits gleich; bei deleted/paused Skip wenn plan bereits free; bei invoice.payment_failed Skip wenn subscription_status bereits past_due. Log: "Webhook skip: user %s already %s for %s". User-Resolution mit Log: "Webhook resolve: event=... resolved_uid=... (meta=..., sub=..., cust=...)". Signaturfehler liefern weiterhin 200 und {"received": True}. Helper _get_profile_by_user_id(user_id) fuer Skip-Logik.
- **Stripe Status -> Plan:** STRIPE_STATUS_TO_PLAN Dict (AlphaCycle entitlement policy): active, trialing, past_due -> paid; canceled, incomplete, incomplete_expired, paused, unpaid -> free. subscription.updated/renewed nutzen dieses Mapping.
- **GET /api/auth/profile:** subscription_status in allen Pfaden: anonymous und Supabase-Fallback liefern subscription_status "inactive". Resolved plan: nie trial wenn trial abgelaufen (effective_plan = free); bei neuem User nach Insert plan trial, trial_ends_at, trial_active true.
- **Frontend:** currentPlan nur aus Backend-Response (fetchUserPlan) oder anonymous bei Sign-Out; applyBlurGates nutzt effectivePlan (trial -> paid uncond.). #upgrade-success: Hash sofort leeren, dann Poll fetchUserPlan alle 3s, max 5 Versuche; bei currentPlan === paid: updateAuthUI, applyBlurGates, Banner "WELCOME TO ALPHACYCLE PRO"; bei max Versuchen: Hinweis "Payment received — please refresh to unlock Pro."

## Letzter Session-Status (2026-03-13) — Track Record Seite (BLOCK2 PROMPT2)
- **Track Record Seite**: Neue View `track-record-view` zwischen landing-view und dashboard-view. Zeigt "Track Record" mit Erklaerung "How the ARC Index works", Timeline mit 4 historischen Signalen (Deep Value Nov 2022, Accumulation Mar 2023, Risk Rising Oct 2024, Current Signal mit id tr-current-detail), Disclaimer und CTA "START 7-DAY FREE TRIAL". showTrackRecord() blendet nur track-record-view ein und scrollt nach oben; showLanding()/showDashboard() blenden track-record-view aus. Auf der Landing unter dem Track-Record-Teaser (3 Karten) Link "View Full Track Record &#8594;" (showTrackRecord). "&#8592; BACK" auf der Track-Record-Seite fuehrt zu showLanding().

## Letzter Session-Status (2026-03-13) — Landing Page (BLOCK2 PROMPT1)
- **Landing Page**: Nicht eingeloggt sieht der Besucher zuerst eine Landing Page (landing-view), eingeloggt das Dashboard (dashboard-view). Navbar bleibt ausserhalb. In index.html: Gesamter Bereich von Ticker-Bar bis Footer in `<div id="dashboard-view">` gewrappt; direkt davor `<div id="landing-view" style="display:none;">` mit Hero (Know exactly where Bitcoin is in the cycle), Live-ARC-Preview (landing-arc-score, landing-arc-zone, landing-btc-price, landing-fg, landing-now-detail), CTA "START 7-DAY FREE TRIAL" (openAuthModal signup), Track-Record-Teaser (3 Beispiele: Dec 2022 Deep Value, Oct 2024 Risk Rising, Now Accumulation), 4 Components (Trend/Drawdown/Sentiment/Liquidity), Pricing ($0 Free / $49/mo Pro mit 7 DAYS FREE Badge), Footer-Link "View Dashboard" (showDashboard). showLanding()/showDashboard() schalten die Sichtbarkeit. Routing: initAuth und onAuthStateChange rufen nach Auth-Status showDashboard() oder showLanding() auf. Landing-Preview wird am Ende von updateUI() aus S.arcSummary/S.btcMarket/S.fgCurrent befuellt. Navbar: Wenn Landing sichtbar und nicht eingeloggt, Button "LOG IN" (openAuthModal login), sonst "FREE ACCESS" (signup).

## Letzter Session-Status (2026-03-13) — 7-Tage Free Trial
- **7-Tage Free Trial**: Jeder neue User erhaelt 7 Tage vollen Zugang; danach gelten Blur Gates fuer Paid-Sections. Backend: `/api/auth/profile` liefert `trial_ends_at`, `trial_active` und setzt bei neuem Profil (nach Insert) `plan: "trial"` mit Trial-Ende jetzt+7 Tage (UTC, ISO). Bei bestehendem Profil: Trial-Logik aus `plan === "free"` und `created_at` (trial_end = created + 7 Tage, trial_active = utcnow < trial_end); effective_plan = "trial" wenn free + trial_active, sonst plan. Import `from datetime import datetime, timedelta` in main.py. Frontend: Globale Variablen `trialActive`, `trialEndsAt`; `fetchUserPlan()` setzt diese aus Profile-Response. `applyBlurGates()` nutzt `effectivePlan` (trial -> paid fuer Lock-Logik): Free-Gates locked bei effectivePlan === 'anonymous', Paid-Gates locked bei effectivePlan !== 'paid'; bei Trial-Usern (currentPlan === 'trial') wird das Paid-Gate-Overlay ausgeblendet (kein Upgrade-Button). Navbar-Badge: Bei `currentPlan === 'trial'` Anzeige "TRIAL · Xd left" mit Tage-Countdown aus trialEndsAt, Styling rgba(0,212,170,0.15) / #00D4AA / Border.

## Letzter Session-Status (2026-03-13) — Kritische Bug-Fixes + Stripe Checkout/Webhook
- **BUG 1 Blur-Gate HTML-Nesting**: Bei drei Gates (gate-hero, gate-cycle-overview, gate-decision-engine) lag die `blur-overlay`-div innerhalb von `blur-content`, wodurch der Overlay-Text mitgeblurt wurde. Korrektur: `blur-content` und `blur-overlay` sind jetzt Geschwister. gate-hero: 2 fehlende `</div>` vor dem blur-overlay ergaenzt; gate-cycle-overview: 1 `</div>` ergaenzt; gate-decision-engine: 1 `</div>` ergaenzt. Alle anderen Gates (gate-historical-returns, gate-near-term, gate-arc-history, gate-arc-momentum, gate-zone-history, gate-content-export) waren bereits korrekt.
- **BUG 2 Gauge Label (hero-risk-label)**: Das Zone-Label unter dem Hero-Gauge (z. B. "DEEP VALUE" vs "ACCUMULATION") wurde zuvor aus `arc_display` abgeleitet. Bei ARC raw 32 ist arc_display ~29.2, phaseOf(29.2) = "Deep Value" (falsch). Zone-Klassifikation muss immer auf dem **rohen ARC Score** (`arc_score`) basieren. In `updateHeroRisk()` in index.html wird fuer `phaseOf()` jetzt `arc_score` (Fallback arc_display, combined, btcScore) verwendet; arc_display bleibt nur fuer die angezeigte Gauge-Zahl (btc-score-val).
- **BUG 3 Blur Gates min-height**: `.blur-gate.locked` hat im Haupt-CSS bereits `min-height: 220px` und `margin-bottom: 16px`. Im @media (max-width: 480px)-Block wurde die Override von 200px/12px auf 220px/16px angepasst, damit locked Blur Gates sich auf Mobile nicht ueberlappen.
- **Stripe Checkout + Webhook (Paid Plan)**: In `backend/requirements.txt` wurde `stripe>=8.0.0` hinzugefuegt. In `backend/main.py` wird Stripe ueber `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` und `STRIPE_PRICE_ID` aus Environment-Variablen konfiguriert (`stripe.api_key = STRIPE_SECRET_KEY`). Neuer Endpoint `POST /api/checkout` (Rate Limit 10/min) erstellt eine Stripe Checkout Session im Subscription-Mode (Price-ID aus `STRIPE_PRICE_ID`, 7 Tage Trial) fuer einen vorhandenen oder neu angelegten Stripe-Customer; die Customer-ID wird in `user_profiles.stripe_customer_id` gespeichert. Neuer Webhook-Endpoint `POST /api/stripe-webhook` (ohne Rate Limiting) validiert Events mit `STRIPE_WEBHOOK_SECRET` und aktualisiert basierend auf Event-Typ (checkout.session.completed, customer.subscription.updated/renewed/deleted/paused, invoice.payment_failed) die Felder `plan`, `subscription_status`, `stripe_customer_id`, `stripe_subscription_id` und optional `current_period_end` in `user_profiles`. Die Zuordnung zum Nutzer erfolgt ueber `supabase_user_id` in den Stripe-Metadaten oder ueber die gespeicherte `stripe_customer_id`.
- **Stripe Frontend (Upgrade-Button + Pricing)**: In `index.html` wurde `openUpgradeModal()` durch eine async-Funktion ersetzt: Prueft ob `currentUser` und Supabase-Session vorhanden sind, sonst oeffnet Auth-Modal (signup/login). Setzt alle Upgrade-Buttons auf "REDIRECTING..." und disabled, ruft `POST /api/checkout` mit Bearer-Token und `user_id`/`email` auf, leitet bei `checkout_url` auf Stripe Checkout weiter; bei Fehler Alert und Button-Reset auf "UPGRADE TO PRO — $49/mo". In `applyBlurGates()`: Paid-Gates zeigen fuer anonyme Nutzer "START 7-DAY FREE TRIAL" (oeffnet Signup), fuer eingeloggte Free-User "UPGRADE TO PRO — $49/mo" (ruft `openUpgradeModal()`); Button-Styles einheitlich #00D4AA. Free-Gates-Button-Text von "UNLOCK FREE" auf "START FREE — NO CARD NEEDED" geaendert. Nach Admin-Param-Check: Bei Hash `#upgrade-success` nach 2s `fetchUserPlan()`, `updateAuthUI()`, `applyBlurGates()` und ein 5s-Banner "WELCOME TO ALPHACYCLE PRO", danach Hash leeren.

## Letzter Session-Status (2026-03-12) — Backend Hardening (Type Hints + Response Cache + Rate Limiting) + Logo-Fix + 1Y Daily ARC Chart + Mobile-First CSS + Blur Gates + Global Data Fixes
- **Logo-Fix**: LOGO_DATA_URL in index.html zeigt nicht mehr auf einen abgeschnittenen Base64-String, sondern auf die Static-URL des Backends: `https://alphacycle-production.up.railway.app/static/logo.jpeg`. Navbar: Vor dem Text-Logo wurde ein `<img class="logo-img" src="" alt="A">` eingefuegt (34x34px, border-radius 6px, onerror versteckt das Bild bei Ladefehler); die bestehende Zeile `document.querySelectorAll('img.logo-img').forEach(...)` setzt die src weiterhin aus window.LOGO_DATA_URL. Loading Screen: load-logo-img auf 48x48px und border-radius 8px vergroessert. Favicon: Beide SVG-Data-URL-Links wurden durch einen einzigen `<link rel="icon" type="image/jpeg" href=".../static/logo.jpeg">` ersetzt. backend/static/logo.jpeg und Static-Mount in main.py unveraendert.
- **Backend Hardening — Type Hints**: In `backend/scoring.py` und `backend/fetcher.py` wurden alle zentralen Funktionen mit Python Type Hints annotiert (`from typing import Optional, Any` plus konkrete Typen wie `list[float]`, `dict[str, float]`, `Optional[dict]` etc.). In `backend/main.py` sind die internen Helper (`_require_cache`, `_clean`, `_prices_to_series`, `_build_ratio_series`, `get_eth_btc_signal`, `compute_zone_history`, `get_zone_name`) ebenfalls typisiert. Die Bodies wurden nicht verändert; es handelt sich ausschließlich um Annotations zur besseren Lesbarkeit und statischen Analyse.
- **Backend Hardening — Rate Limiting (slowapi)**: `slowapi>=0.1.9` wurde zu `backend/requirements.txt` hinzugefügt. In `backend/main.py` ist ein globaler `Limiter` mit `key_func=get_remote_address`, `default_limits=["100/minute"]` und `storage_uri="memory://"` konfiguriert und an `app.state.limiter` gehängt; `RateLimitExceeded` wird über `_rate_limit_exceeded_handler` behandelt. `/health` ist via `@limiter.exempt` ausgenommen. Alle Endpoints akzeptieren nun einen `request: Request` Parameter, damit slowapi die IP bestimmen kann. Heavy-Endpoints sind strenger limitiert: `/api/analyzer`, `/api/decision`, `/api/snapshot` mit `30/minute`, `/api/subscribe` mit `10/minute`, `/api/auth/profile` mit `20/minute`; alle anderen ziehen den Default `100/minute`.
- **Backend Hardening — Response Cache (15s TTL)**: Für die heavy Compute-Endpunkte `/api/analyzer`, `/api/decision` und `/api/snapshot` existiert in `backend/main.py` ein eigener In-Memory-Response-Cache (`_response_cache: dict[str, tuple[timestamp, dict]]`), gesteuert über `_get_cached_response(key)` und `_set_cached_response(key, data)`. Jeder dieser Endpoints prüft am Anfang auf einen validen Eintrag (TTL `_RESPONSE_TTL = 15.0` Sekunden) und gibt dann sofort die gecachte JSON-Antwort zurück; nach erfolgreicher Berechnung wird das Ergebnis in `_response_cache` abgelegt. Nach einem erfolgreichen Daten-Refresh in `refresh_cache()` wird `_response_cache.clear()` aufgerufen, so dass alle heavy-Responses nach neuen Daten berechnet werden. Alle bestehenden Bodies (Analyzer, Decision Engine, Snapshot-Build) bleiben inhaltlich unverändert.
- **R3-F — 1Y Daily ARC Chart (echte Tageswerte)**: Der Endpoint `/api/history-daily` in `backend/main.py` liefert jetzt **echte tägliche ARC-Scores** und ruft dafür `run_daily_backtest(days=365)` aus `backend/services/backtest_engine.py` auf. `run_daily_backtest` holt tägliche BTC-Candles von Kraken (interval=1440), verwendet die wöchentliche 200W-MA aus dem bestehenden Backtest-Cache (letzter bekannter Wert pro Tag), berechnet den Drawdown-Score auf Basis der gesamten Preis-Historie bis zum jeweiligen Tag, nutzt die vollständige Fear-&-Greed-Historie von Alternative.me (tägliche Werte, forward-filled bei Lücken) und die FRED-Net-Liquidity-Serie (WALCL − TGA − RRP, wöchentliche Werte, per Date-Alignment und Forward-Fill). Für jeden Tag wird der ARC exakt mit der gelockten Formel berechnet (`ma_200w*0.35 + drawdown*0.25 + macro_liq*0.25 + fg_score*0.15`), auf 0–100 geclamped und zusätzlich `score_display = arc_display_score(arc)` ausgegeben. Im Endpoint wird der letzte Punkt wie bisher mit dem aktuellen Live-ARC aus `CACHE["combined"]["combined_score"]` und dem letzten BTC-Preis aus dem Cache überschrieben, so dass das Ende der 1Y-Kurve immer mit der Hero-Gauge übereinstimmt. Das Ergebnis `{date, price, score, score_display}` für ~365 Tage wird in `CACHE["daily_history"]` gespeichert und bei jedem erfolgreichen `refresh_cache()` via `CACHE.pop("daily_history", None)` invalidiert.
- **Mobile-First Dashboard CSS**: Am Ende des `<style>`-Blocks in `index.html` wurden zusätzliche Media Queries für `max-width: 480px`, `max-width: 768px` und `max-width: 360px` ergänzt. Für kleine Geräte (bis 480px) werden Navbar (kompakter, Zeit + Tour-Button versteckt, Refresh-Button nur als Icon), Ticker, Container-Padding, Hero-Card, Factor-Gauges (2x2-Grid), Zone-Bar (horizontales Scrollen mit Snap), Decision Engine, Historical Returns, Cycle Overview, Near-Term Outlook, ARC Chart-Höhe, Zone History Table (horizontal scrollen) und Data Inspector gezielt enger und besser lesbar gestaltet. Für alle mobilen Breakpoints werden Touch-Targets auf mindestens ~36px Höhe vergrößert, horizontale Scrollbars in den horizontal scrollbaren Grids ausgeblendet und Overflow-x auf `html, body` verhindert. Für sehr kleine Displays (≤360px) werden Hero-Gauge-Zahl, Decision-Grid (einspaltig) und minimale Breiten von Zonenboxen weiter reduziert. Ein zusätzlicher 480px-Block optimiert explizit die Hero-Zone-Bar (horizontal scroll + Snap), Factor-Gauges (2x2), die Zonentabelle, den Auth-Modal und den Footer; ein 768px-Block ergänzt Touch-Targets (mind. 36px) und blendet horizontale Scrollbars aus, und ein 360px-Block komprimiert Decision-Grid und Zonenbreiten weiter.
- **Zone History — 4-Wochen-Minimum + Live-Zone-Hinweis**: In `backend/main.py` wurde `compute_zone_history()` so umgebaut, dass ein Zonenwechsel erst dann als neue Periode bestätigt wird, wenn der ARC mindestens 4 aufeinanderfolgende Wochen in der neuen Zone verbleibt (`min_weeks=4`). Kürzere Grenz-Überschreitungen werden in die vorherige Zone absorbiert; die erste Zone wird ohne Minimum übernommen, die laufende Zone wird als „ongoing“ geschlossen. Der Endpoint `/api/zone-history` liefert weiterhin `zone_history`, `current_zone`, `current_zone_since`, `current_zone_weeks`, ergänzt diese Felder aber jetzt um `live_zone` und `live_zone_confirmed`: Wenn der Live-ARC (`combined_score`) bereits in einer anderen Zone liegt als die zuletzt bestätigte Backtest-Zone, wird `live_zone` auf die Live-Zone gesetzt und `live_zone_confirmed = False`, ansonsten entspricht `live_zone` der bestätigten Zone und `live_zone_confirmed = True`. Im Frontend (`renderZoneHistory()` in `index.html`) wird dieser Zustand genutzt, um entweder die bestätigte Zone mit Dauer („Current: ZONE for X weeks…“) oder — bei abweichender Live-Zone — einen Hinweis „Confirmed: [ZONE] … — Live ARC entering [LIVE_ZONE]“ in den passenden Zonenfarben anzuzeigen.
- **Supabase Blur Gates aktiviert**: `initAuth()` ruft jetzt nach erfolgreichem Session-Fetch und `updateAuthUI()` auch `applyBlurGates()` auf und registriert den gleichen Aufruf im `onAuthStateChange`-Listener, so dass Free-/Paid-Gates unmittelbar auf Auth-Änderungen reagieren. Im `boot()`-Finally-Block wird `initAuth()` mit `await` aufgerufen, Fehler geloggt (`console.warn('Auth init failed:', e)`), und falls `supabaseClient` nicht initialisiert werden kann, wird `applyBlurGates()` trotzdem einmalig aufgerufen, damit anonyme Nutzer die Free-/Paid-Gates korrekt als geblurrte Sections sehen.
- **Global Data / BTC Dominance (CoinCap)**: `backend/fetcher.py` nutzt in `fetch_global_data()` jetzt die CoinCap v2 API (`https://api.coincap.io/v2/assets?limit=5`), um echte BTC-Dominanz und eine grobe Total-Market-Cap abzuleiten. Aus den Top-5-Assets wird die Summe der MarketCaps gebildet und als ~78 % des Gesamtmarkts interpretiert (`total_mc = sum_top5 / 0.78`); daraus wird `btc_dominance = btc_mc / total_mc * 100` gerundet berechnet. Zusätzlich werden `total_market_cap`, `total_volume_24h` (aus `volumeUsd24Hr`) und `market_cap_change_24h` (aus `changePercent24Hr`) gesetzt; bei Fehlern oder fehlenden Daten fällt die Funktion auf den bisherigen Default (`btc_dominance: 55.0`) zurück.
- **FRED Label-Logik korrigiert**: Das `src-fred` Label in `index.html` zeigt im Backend-Pfad jetzt immer `"FRED"` mit Klasse `status-src`, unabhängig von `S.walclCurrent`, da das Backend grundsätzlich reale FRED-Daten (oder dokumentierte synthetische WALCL-Fälle) verwendet. Der "FRED (synthetic fallback)"-Text bleibt ausschließlich im reinen Frontend-Fallback (ohne Backend) aktiv, wo `syntheticWALCL()` eingesetzt wird; dort bleibt die bisherige Warn-Logik erhalten.

## Letzter Session-Status (2026-03-04) — Logo Base64 inline + Vier Bugfixes + ARC Chart Zonenfarben
- **5-Zonen-System**: phaseOf() und alle Zone-Labels/Farben auf 5 Zonen umgestellt: Deep Value (0-30, #00DC78), Accumulation (30-40, #00B4D8), Expansion (40-60, #58A6FF), Risk Rising (60-70, #FF9500), Euphoria (70-100, #FF3B3B). Hero Card zeigt Zone-Namen aus phaseOf(arc_display). Cycle Phase Guide und Historical ARC Returns mit 5 Boxen. Backend: historical_returns.py 5 Zonen (deep_value, accumulation, expansion, risk_rising, euphoria) mit zone_name; main.py get_zone_name() und arc-summary.zone_name; backtest_engine.py ZONES/ZONE_NAMES. compute_arc_score/arc_display_score unveraendert.
- **Logo Base64 dauerhaft / Logo-Fix (2026-03-11)**: LOGO_DATA_URL in index.html zeigt auf die Static-URL `https://alphacycle-production.up.railway.app/static/logo.jpeg` (kein Base64 mehr, da der bisherige String abgeschnitten war). window.LOGO_DATA_URL wird im ersten <script> im <head> gesetzt. Navbar: <img class="logo-img" src="" alt="A"> neben dem Text-Logo (34x34px), src wird per DOMContentLoaded aus window.LOGO_DATA_URL gesetzt; onerror versteckt das Bild bei Ladefehler. Loading-Screen: load-logo-img (48x48px, border-radius 8px), src wie bisher aus LOGO_DATA_URL. Favicon: einziges <link rel="icon" type="image/jpeg" href=".../static/logo.jpeg">. Backend: app.mount("/static", StaticFiles(directory=backend/static)); logo.jpeg bleibt dort.
- **ARC History Chart Zonenfarben**: Chart.js ARC-Hintergrund als **klar getrennte Zonen** (kein Gradient): Plugin `zoneRects` (beforeDraw) zeichnet 5 Rechtecke mit ctx.fillRect: 0–30 rgba(16,185,129,0.50) (sattes Grün), 30–40 rgba(4,120,87,0.45) (dunkleres Grün), 40–60 rgba(88,166,255,0.28), 60–70 rgba(255,149,0,0.42), 70–100 rgba(255,59,59,0.50). Trennlinien 1px weiss alpha 0.15 bei y=30, 40, 60, 70. Legende: 0-30 Deep Value (#10B981) | 30-40 Accumulation (#047857) | 40-60 Expansion (#58A6FF) | 60-70 Risk Rising (#FF9500) | 70-100 Euphoria (#FF3B3B). **Live Position Dot**, **Zoom & Pan**, Zone-Labels rechts unveraendert.
- **ARC History Chart Zonenfarben & Interaktion**: Chart.js ARC-Hintergrund als **klar getrennte Zonen** (kein Gradient): Plugin `zoneRects` (beforeDraw) zeichnet 5 Rechtecke mit ctx.fillRect: 0–29.5 rgba(0,212,170,0.42), 29.5–39.5 rgba(0,180,216,0.38), 39.5–59.5 rgba(88,166,255,0.28), 59.5–69.5 rgba(255,149,0,0.42), 69.5–100 rgba(255,59,59,0.50). Trennlinien 1px weiss alpha 0.15 bei y=29.5, 39.5, 59.5, 69.5. Legende: 0-29 Deep Value (#00D4AA) | 30-39 Accumulation (#00B4D8) | 40-59 Expansion (#58A6FF) | 60-69 Risk Rising (#FF9500) | 70-100 Euphoria (#FF3B3B). **Live Position Dot**, **TradingView-style Zoom & Pan**: Chart.js 4.x + hammer.js + chartjs-plugin-zoom@2.x, Zoom nur auf der X-Achse (mode 'x', Y-Achse fix), wheel/pinch Zoom (speed 0.1), Pan per Drag (threshold 5), `limits.x.min/max = 'original'`. Das Zoom-Plugin wird einmalig nach dem Laden der Scripts via `if (window.ChartZoom) { Chart.register(window.ChartZoom); } else if (window['chartjs-plugin-zoom']) { Chart.register(window['chartjs-plugin-zoom']); }` registriert; der eigentliche Chart wird als `window._arcHistoryChart` erstellt und zusätzlich als `window.arcChart` global referenziert. 1Y/10Y Toggle ruft vor Re-Render `resetZoom()` auf, der Reset-Button "↺ RESET" neben „↓ EXPORT PNG“ sowie ein Doppelklick auf den Chart rufen ebenfalls `resetZoom()` auf (via `window.arcChart`). Canvas-Cursor: crosshair, beim Drag grabbing. (Optionales) Zoom-Hint Overlay "ZOOMED — dbl-click to reset" wird angezeigt, solange gezoomt ist.
- **Historical ARC Returns Präsentation (R3-B)**: index.html HISTORICAL ARC RETURNS: Über jeder Zone-Box ein Kontext-Satz (Deep Value: "Historically strongest entry zone", Accumulation: "High probability long-term returns", Expansion: "Moderate upside, increasing risk", Risk Rising: "Reduce exposure — late cycle", Euphoria: "Avg -40% drawdown from peak"). Aktuelle Zone hervorgehoben: 2px solid Border in Zone-Farbe + "YOU ARE HERE" Badge oben rechts; applyHistoricalReturnsCurrentZone() nutzt dabei strikt den **rohen ARC Score (`arc_score`)** (oder `combined`-Fallback), NICHT `arc_display`, damit die Zone-Klassifikation immer auf 0–29/30–39/40–59/60–69/70–100 basiert (z. B. ARC 32 → Accumulation, auch wenn arc_display ~29 ist). Unter den Boxen: "Based on {total_entries} historical zone entries since 2017." (total_entries = Summe aller entry_count). Nur index.html, Daten aus S.historicalReturns.
- **Liquidity Impulse (R3-C)**: scoring.py compute_arc_score(): macro_liq fuer ARC-Formel aus Impuls (Richtung/Staerke der Net-Liquidity-Aenderung). Bei >=22 Punkten: change_30d = (net_liq[-1]-net_liq[-22])/net_liq[-22]*100, bei >=65 Punkten zusaetzlich change_90d = (net_liq[-1]-net_liq[-65])/net_liq[-65]*100; impulse_score = 50 - change_30d*2.5 - change_90d*1.5, clamp(0,100). Fallback bei zu wenig Daten: bisherige macro_liq aus compute_btc_score(). compute_btc_score() und ARC-Gewichte unveraendert. Backtest-Cache wird durch main.py lifespan (/tmp/backtest_cache.json loeschen) beim Start neu aufgebaut.
- **Expected Range (12M)**: main.py _get_expected_range(arc, hist_returns, high_risk_drawdown) zeigt immer historische Zone-Statistik aus Backtest, unabhaengig von Phase. Kein bear_wait mehr. Response: type (forward_return | reduce | drawdown), label, sublabel (win rate + entries), zone. Zonen nach ARC: <30 Deep Value, <40 Accumulation, <60 Expansion, <70 Risk Rising (REDUCE-Label), >=70 Euphoria (Drawdown-Warnung). Bei fehlendem Cache: Fallback Zone-Name ohne Return-Wert. Phase-Logik fuer position/allocation unveraendert.
- **BUG 1 Logo / Logo-Fix**: index.html nutzt LOGO_DATA_URL = Static-URL (https://alphacycle-production.up.railway.app/static/logo.jpeg). Navbar zeigt <img class="logo-img"> neben Text-Logo; Favicon ist type="image/jpeg" auf dieselbe URL. Loading-Screen und img.logo-img werden per Script mit window.LOGO_DATA_URL befuellt. Kein Base64 mehr in index.html (war abgeschnitten).
- **BUG 2 Bear+ARC Accumulation**: get_arc_summary() BEAR_PHASES nutzt arc_raw-Schwellen: arc_raw>40 → WAIT — Bear Market, 0-20%, Low; arc_raw>30 → LOW ACCUMULATION, 20-35%, Low-Moderate; arc_raw>25 → ACCUMULATION, 35-50%, Moderate; sonst STRONG ACCUMULATION, 50-70%, Moderate-High. ACCUMULATION_PHASES und BULL_PHASES unveraendert. ARC-Formel/compute_arc_score/arc_display_score unveraendert.
- **BUG 3 Tactical-Konsistenz**: /api/arc-summary liefert bei Bear-Phasen `tactical_label` und `tactical_color` (Wait: "Bear Market — Wait for lower ARC", #6b7280; Accumulation-Zonen: #10b981). index.html Cycle Overview (cp-tactical) und Near-Term Card (st-tactical) nutzen S.arcSummary.tactical_label/tactical_color falls vorhanden, sonst S.shortTermContext (analyzer).
- **BUG 4 Content Export aus Live-Daten**: Content Export zeigt einen einzigen Button "COPY DATA". buildDataBlock() erzeugt einen sauberen Daten-Block (kein Tweet, keine Emojis/Hashtags) aus S.* mit: Date (YYYY-MM-DD), ARC Index, Zone, Phase, BTC Price, Fear & Greed, Percentile, Position, Allocation, 12M Return (this zone), Win Rate, Days Since Top, Est. Cycle Bottom. copyDataBlock() kopiert den Text in die Zwischenablage; Button zeigt kurz "COPIED ✓" dann zurueck zu "COPY DATA". Vorschau (ce-preview, <pre>) zeigt den Daten-Block in Monospace (var(--f-mono)). updateContentPreview() setzt den Inhalt aus buildDataBlock(). formatPrice/getZoneLabelByArc/ordinal Hilfsfunktionen; S.historicalReturns.zones fuer avg_12m/win_rate_12m; days_since_top aus S.arcSummary/shortTermContext; Est. Cycle Bottom aus festem Fenster (2026-10-01). snapshot.py unveraendert.

**FIX 57**: phaseOf() und getZoneLabelByArc() nutzen strikt `< 30` als Deep-Value-Grenze. Hero-Zonenlabel und Phase-Banner leiten die Zone jetzt aus dem **raw ARC Score (`arc_score`)** ab (Gauge/Zahl weiter aus `arc_display`), sodass ein ARC um 32 immer als "Accumulation" im 5-Zonen-System erscheint. Der fruehere Bear-Phase-Override im Hero (`updateHeroRisk()`), der bei Bear-Phasen und niedrigem ARC einen Phasen-Text statt des Zonen-Namens setzte, wurde entfernt: das Hero-Label zeigt nun **immer** den Zonen-Namen aus `phaseOf(arcRaw)` (Deep Value / Accumulation / Expansion / Risk Rising / Euphoria), unabhaengig von der Phase; separate Cycle-Signale werden weiterhin ueber den eigenen Badge-Block gerendert.
**FIX 58**: BTC-Komponentenkarte "Fear & Greed" zeigt nun ausschließlich den **rohen Alternative.me-Wert** (z. B. `15`) an. Der intern berechnete ARC-Komponenten-Score für F&G bleibt nur für die ARC-Formel sichtbar (Decision Engine, Data Inspector), wird aber nicht mehr in der Hero-Komponentenbox angezeigt, um Verwirrung zu vermeiden.

**Zone-Grenzen ganzzahlig (0-29 / 30-39 / 40-59 / 60-69 / 70-100)**: phaseOf(), scoreColor(), getZoneLabelByArc() und Backend (get_zone_name, _get_expected_range, historical_returns in_zone/zone_meta, backtest_engine ZONES) nutzen einheitlich <=29 Deep Value (#00C896), <=39 Accumulation (#00B4D8), <=59 Expansion (#3B82F6), <=69 Risk Rising (#F97316), >=70 Euphoria (#EF4444). ARC Chart Zonen-Y-Achse: Trennlinien bei 29.5, 39.5, 59.5, 69.5; Legende und hr-grid 0-29, 30-39, 40-59, 60-69, 70-100. Hero-Zonenleiste (unter der Hauptkarte) zeigt dieselben Bereiche: 0–29 / 30–39 / 40–59 / 60–69 / 70–100. Hero-Card-Zonenname, Cycle-Overviews und Zone-History-Current-Label nutzen überall dieselben Grenzen (ARC 32 → „Accumulation“) und die neuen Zonenfarben mit stärkerer Progression (Emerald → Teal → Blue → Orange → Red).
**Indicator Radial Gauges**: BTC-Komponentenkarte (200W MA Dev, Drawdown, Fear & Greed, Liquidity) nutzt kompakte Halbkreis-Gauges (SVG, Radius 28, strokeWidth 6) pro Faktor statt horizontaler Balken. Gauge-Farbe folgt den Zonenfarben auf Basis des Komponentenwerts (<=29 Deep Value #00D4AA, <=39 Accumulation #00B4D8, <=59 Expansion #58A6FF, <=69 Risk Rising #FF9500, >=70 Euphoria #FF3B3B); Arc-Länge proportional zum Wert, darunter die gerundete Zahl. Die vier Factor Cards sind als eigene `factor-card`-Blöcke im Hero eingebaut; pro Karte wird der Gauge per `buildGaugeSVG`/`updateGauge` (IDs `gauge-ma/dd/fg/liq` und `val-ma/dd/fg/liq`) gerendert.
**Logo Fallback / Logo-Fix (2026-03-11)**: LOGO_DATA_URL = Static-URL (Backend /static/logo.jpeg). Navbar: <img class="logo-img"> (34x34px) neben dem Text-Logo „AlphaCycle“ + Tagline; src wird aus window.LOGO_DATA_URL gesetzt, onerror versteckt das Bild. Loading Screen: load-logo-img 48x48px, border-radius 8px. Favicon: einziges <link rel="icon" type="image/jpeg" href=".../static/logo.jpeg">. Bestehende Zeile document.querySelectorAll('img.logo-img').forEach(...) bleibt; keine kaputten Base64-Referenzen mehr.
**Bottom Formation (Bear-Phasen)**: get_arc_summary() setzt bottom_formation = True wenn Phase in BEAR_PHASES und (days_since_top >= 300 ODER (days_since_top >= 150 UND drawdown_from_top <= -0.40)). Bei bottom_formation Allocation/Position eine Stufe aggressiver (arc_raw >39 -> LOW ACCUMULATION statt WAIT, etc.). Response: bottom_formation (bool), bottom_formation_note (String). index.html Decision Engine: Badge "Bottom Formation Signal" (#00B4D8) unter Suggested Position wenn bottom_formation === true.
**Saisonalität (BTC Seasonal Patterns)**: backend/seasonality.py mit MONTHLY_BIAS und get_seasonal_context() (month, month_name, avg_return, label, color, next_month_return). main.py bindet get_seasonal_context() ein; /api/arc-summary liefert "seasonality": {...}. Saisonalität beeinflusst ARC/Decision nicht. index.html Near-Term Outlook Card (30–90D) zeigt unter dem CONDITIONS SCORE Block eine Zeile "SEASONALITY" mit "[Month] — [label] ([avg_return]% avg)" und Farbe aus seasonality.color.

**ETH/BTC Ratio Signal**: main.py get_arc_summary() berechnet das aktuelle ETH/BTC-Verhältnis aus den Live-Preisen (eth_price/btc_price) und gibt ein neues Feld `eth_btc_signal` zurück (ratio, label, note, color, strength). Schwellen: <0.020 "ETH Extreme Undervaluation" (starkes Akkumulations-Signal, #00D4AA), <0.030 "ETH Undervalued vs BTC" (moderates Akkumulations-Signal, #00B4D8), <0.040 "ETH Neutral vs BTC" (neutral, #6b7280), <0.060 "ETH Elevated vs BTC" (BTC-Dominanz wahrscheinlich, Vorsicht, #FF9500), ≥0.060 "ETH Overvalued vs BTC" (Altseason-Peak, meiden, #FF3B3B). index.html Near-Term Outlook Card zeigt im selben Block wie die Saisonalität eine Zeile "ETH/BTC RATIO" mit Hauptzeile "[ratio] — [label]" in eth_btc_signal.color und einer zweiten, kleineren grauen Zeile mit dem Note-Text; beide stehen direkt unter dem CONDITIONS SCORE/Badge. In der Navbar-Ticker-Leiste wird der ETH/BTC-Wert farblich anhand `eth_btc_signal.strength` hervorgehoben: strong/moderate → #00B4D8, caution → #FF9500, avoid → #FF3B3B, neutral bleibt Standardfarbe.

**ARC Zone History Table**: backend/main.py stellt einen Endpoint `/api/zone-history` bereit, der aus den gecachten Backtest-Ergebnissen (`backtest_results`) eine woechentliche ARC-Historie aufbaut und mit `compute_zone_history()` zu zusammenhaengenden Zonenperioden gruppiert (Zone, from, to, weeks, btc_entry, btc_exit, return_pct). `compute_zone_history()` verwendet ausschliesslich den **rohen ARC-Score** (`score`/`arc_score`) und `get_zone_name()` (<=29 Deep Value, <=39 Accumulation, <=59 Expansion, <=69 Risk Rising, >=70 Euphoria) als einzige Zonen-Quelle, bestimmt BTC Entry-Preis als Preis am ersten Tag der Zone, BTC Exit-Preis als Preis am letzten Tag der Zone (oder letztem verfuegbaren Tag bei laufender Periode) und berechnet `weeks` robust auf Basis der Datumsdifferenz (`abs(days)//7`, mind. 1). Die Funktion gibt maximal die **letzten 20 Zonenperioden** in absteigender Reihenfolge zurueck (neueste zuerst), wobei die laufende Periode `to = null` hat. Der Endpoint-Response enthaelt: `zone_history`, `current_zone`, `current_zone_since`, `current_zone_weeks` (immer aus der ersten, aktuellsten Periode). index.html fuegt nach dem ARC Momentum-Chart eine Section "ZONE HISTORY" ein: Headline "ZONE HISTORY — How long BTC spent in each zone". In `renderZoneHistory()` wird `current_zone` zwar aus dem Backend gelesen, aber bei Bedarf durch die **Live-Zone** aus `S.arcSummary.arc_score` ueberschrieben (Backtest ist woechentlich und kann leicht hinterherhinken); in diesem Fall zeigt die Unterzeile nur "Current: [ZONE]" ohne Wochen/Datum, um keine falschen Zeitrauminformationen zu suggerieren. Die Tabelle selbst bleibt auf den Backtestperioden basierend (inkl. hervorgehobener laufender Periode), max. 20 Eintraege, vertikal scrollbar (max-height ~400px).

**Onboarding Tooltip Tour**: index.html enthaelt eine 4-stufige Onboarding-Tour, die beim ersten Besuch automatisch gestartet wird (nach erfolgreichem Initial-Load, einmalig; State via `localStorage.alphacycle_onboarded = 'true'`). Steps: (1) Hero ARC Index (`#btc-card`) — "The ARC Index"; (2) Decision Engine (`#decision-card`); (3) Historical ARC Returns (`.hist-returns-card`); (4) ARC History Chart (`#arc-chart-card`). Der fruehere Content-Export-Step wurde entfernt. Jeder Step zeigt ein halbtransparentes Overlay mit hervorgehobener Karte (Highlight-Box mit Border + Shadow) und einen Tooltip (max 320px, Hintergrund #1a2233, Border #00D4AA, runde Ecken, Shadow), inklusive Step-Indikator "X / 4", Titel (Monospace uppercase) und Beschreibungstext. Buttons: links "SKIP TOUR" (grau), rechts "NEXT →" (Brand-Farbe) bzw. im letzten Schritt "GOT IT ✓". Beim Skip oder Abschluss wird `alphacycle_onboarded` gesetzt und die Tour nicht mehr automatisch gestartet; ein "?"-Button in der Navbar rechts neben REFRESH erlaubt jederzeit einen manuellen Neustart (setzt `alphacycle_onboarded` zurück und beginnt die Tour neu). Tooltip-Positionierung: Scroll zuerst das Ziel-Element mit `scrollIntoView({behavior:'smooth', block:'center'})` in den Viewport, dann wird der Tooltip mit einer eigenen `positionTooltip(targetEl)`-Funktion (position: fixed) so berechnet, dass er immer vollstaendig im sichtbaren Viewport bleibt (vertikal ggf. unter/ueber dem Element oder zentriert, horizontal geclamped an die Viewport-Breite).

**Supabase Client + Schema**: backend/database.py enthaelt einen Supabase-Client (`supabase`) mit Defaults aus Umgebungsvariablen (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; URL-Default = `https://epcvkgtneeafgpjjrfiq.supabase.co`). Die Initialisierung ist jetzt **lazy/optional**: `supabase = None`, dann nur `create_client(...)` wenn `SUPABASE_SERVICE_ROLE_KEY` gesetzt ist; bei Fehler wird ein Logging-Warning ausgegeben, das Backend startet trotzdem weiter (kein Crash beim Import ohne Key). Die Datei dokumentiert das komplette SQL-Schema als Kommentar (Tabellen `email_captures`, `user_profiles`, `alert_log` inkl. RLS und Policies fuer user_profiles). backend/main.py importiert den Client robust via Try/Except (`from database import supabase`) und guarded alle Supabase-Nutzungen mit `if supabase: ... else: logger.warning("Supabase not configured")` (z. B. `/api/subscribe` und `/api/auth/profile`). In `backend/requirements.txt` ist Supabase jetzt als `supabase>=2.4.0` definiert; `httpx` wird mit `httpx>=0.25.0` eingebunden, um Versionskonflikte mit der bisherigen `supabase==2.3.0`-Abhängigkeit (httpx<0.25.0) zu vermeiden.

**Email Capture (ohne Beehiiv Sync)**: backend/main.py bietet einen POST-Endpoint `/api/subscribe`, der ein `SubscribeRequest`-Model (Pydantic `BaseModel`, Felder `email`, `source="dashboard"`) akzeptiert. Der Endpoint validiert die Email grob (`"@"` und `"."`), liest das aktuelle ARC-Summary via `get_arc_summary()` wieder und legt/aktualisiert dann einen Eintrag in der Supabase-Tabelle `email_captures` per `upsert` (Felder: `email`, `source`, `arc_score` aus `arc_display`, `zone` aus `zone_name`). Externe Beehiiv-Syncs werden nicht mehr serverseitig ausgelöst; der Endpoint gibt nach erfolgreichem Upsert nur noch `{"success": True, "message": "Successfully subscribed"}` zurück. backend/requirements.txt enthaelt `supabase==2.3.0` und `pydantic[email]` fuer Email-Validierungs-Extras.

**Supabase Auth Middleware + Profil-Endpoint**: backend/auth.py enthaelt eine leichte Auth-Schicht um Supabase JWTs zu verifizieren: ein `HTTPBearer`-Scheme (`security = HTTPBearer(auto_error=False)`), ein optionaler `supabase_admin`-Client (lazy init nur bei vorhandenem Service-Role-Key; bei Fehler Logging-Warning, kein Crash) und drei Helferfunktionen: `get_current_user` (liest Supabase-User aus `supabase_admin.auth.get_user(token)` oder gibt `None`, wenn kein Client vorhanden ist), `require_auth` (wirft 401 bei fehlendem/ungueltigem User) und `require_paid` (liest `user_profiles.plan` aus Supabase und wirft 403, wenn der Plan nicht `paid` ist; ohne konfigurierten Supabase-Client 503). In backend/main.py werden diese Funktionen robust importiert und ein Endpoint `GET /api/auth/profile` registriert, der den aktuellen User via `user = Security(get_current_user)` injiziert. Ohne Token: `{authenticated: False, plan: "anonymous"}`. Mit Token und konfiguriertem Supabase: User-Profil aus `user_profiles` laden (oder bei erstem Mal anlegen) und JSON-Response mit `authenticated`, `plan`, `email` und `subscription_status` zurueckgeben; ohne Supabase-Client wird ein einfacher Free-Fallback `{authenticated: True, plan: "free", email}` zurückgegeben, aber kein Datenbankzugriff ausgeführt. Dieses Profil ist die zentrale Quelle fuer Spaeteres Billing/Feature-Gating.

**Frontend Auth Modal (Supabase JS)**: index.html bindet `@supabase/supabase-js@2` per CDN im `<head>` ein und initialisiert im Hauptscript einen Browser-Client (`supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)` mit fixer URL und Platzhalter-ANON-Key). Globaler Auth-State: `currentUser` (Supabase-User), `currentPlan` (`anonymous`/`free`/`paid`) und `authMode` (`signup`/`login`). `initAuth()` ruft `supabaseClient.auth.getSession()` auf, setzt User/Plan (via Backend-Endpoint `/api/auth/profile`) und registriert einen `onAuthStateChange`-Listener; nach jedem State-Wechsel werden `updateAuthUI()` (Navbar) und spaeter `applyBlurGates()` aufgerufen. In der Navbar gibt es rechts neben REFRESH einen neuen Block `#nav-auth`: Button „FREE ACCESS“ (öffnet Signup-Modal) sowie im eingeloggten Zustand ein kleines User-Panel mit Plan-Badge (FREE/PRO), Email und SIGN OUT-Button.

**Auth Modal + Email Capture**: index.html enthaelt ein vollstaendiges Auth-Modal (`#auth-modal`) mit Tabs „CREATE ACCOUNT“ / „LOG IN“, Email- und Password-Feldern, Submit-Button und Fehlertext. `switchTab(mode)` wechselt Texte/Styles fuer Signup vs. Login. `handleAuthSubmit()` nutzt `supabaseClient.auth.signUp` bzw. `signInWithPassword` und zeigt Fehler im Modal an; bei erfolgreichem Signup wird zusaetzlich ein POST auf `/api/subscribe` (Backend) mit `{ email, source: 'signup' }` gesendet, um den Email-Capture-Flow auszulösen. `openAuthModal(mode)`/`closeAuthModal()` steuern Sichtbarkeit. `updateAuthUI()` blendet im Navbar je nach `currentUser` entweder den FREE-ACCESS-Button oder das User-Panel (inkl. Plan-Badge) ein. `handleSignOut()` ruft `supabaseClient.auth.signOut()`, setzt State zurueck und aktualisiert die UI. `initAuth()` wird im `boot()`-Finally-Block nach dem Content-Export-Check aufgerufen, sodass Auth-Status direkt nach dem ersten Daten-Load initialisiert wird.

**Blur Gates (Free vs. Paid Sections)**: index.html enthaelt ein generisches Blur-Gate-System, das bestimmte Sections je nach `currentPlan` (anonymous/free/paid) weich sperrt. CSS: `.blur-gate` als Wrapper, `.blur-content` fuer den Originalinhalt, `.blur-gate.locked .blur-content` mit `filter: blur(6px)` + deaktivierten Pointer-Events, `.blur-overlay` als halbtransparenter Overlay mit Titel und Call-to-Action-Button. `applyBlurGates()` definiert zwei Gruppen: Free-Gates (`gate-historical-returns`, `gate-cycle-overview`, `gate-arc-history`, `gate-near-term`, `gate-live-prices`, `gate-arc-momentum`) werden fuer `currentPlan === 'anonymous'` geblurrt, Paid-Gates (`gate-decision-engine`, `gate-zone-history`, `gate-content-export`) fuer alle ausser `paid`. Je Gate wird Overlay-Text und Button dynamisch gesetzt: fuer anonyme Nutzer immer „🔒 FREE FEATURE“ + „CREATE FREE ACCOUNT“ (öffnet `openAuthModal('signup')`), fuer Free-User an Paid-Gates „⚡ PRO FEATURE“ + „UPGRADE TO PRO — $19/mo“ (ruft `openUpgradeModal()`, aktuell ein Alert-Placeholder). Geblurrte Sections: Historical ARC Returns, Cycle Overview, ARC History Chart + ARC Momentum, Near-Term Outlook, Live Prices (Free-Gates) sowie Decision Engine, Zone History und Content Export (Paid-Gates). Hero-ARC-Card und Navbar bleiben immer voll sichtbar; alle Daten werden weiterhin normal geladen, nur die UI ist interaktiv gesperrt.

## Frühere Sessions (vor 2026-03-04)
- **ARC High/Low Engine (weekly extrempoint detection)**: arc_display_score k=1.2 (optimal fuer Extrempunkte). scoring.drawdown_score_hl(prices, price_override) fuer optionalen Preis (Bottom-Erkennung). compute_arc_score(..., weekly_high=None, weekly_low=None): NACH compute_btc_score() Ueberschreiben von ma_score mit ma_deviation_score(weekly_high, ma_200w) und dd_score mit drawdown_score_hl(prices, weekly_low) wenn high/low vorhanden. compute_btc_score() unveraendert (Permanent Fix). backtest_engine: MA-Score auf weekly_high, Drawdown auf weekly_low via drawdown_score_hl; results mit high/low/score_display. main.py: compute_arc_score mit weekly_high=None, weekly_low=None (Live: Fetcher liefert kein weekly high/low, Fallback auf Close). Chart: ARC-Linie auf score_display, BTC High-Low Band, TOP/BOTTOM Annotationen mit result.high/result.low.
- **HiDPI Chart Rendering**: index.html ARC History Chart und Momentum Chart nutzen Chart.js `devicePixelRatio: window.devicePixelRatio || 2` fuer scharfe Darstellung auf Retina/HiDPI; `.arc-chart-canvas` mit `image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;`; global `:root` mit `-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility;`.
- **Short Term UX Reframe**: Short Term Section heisst jetzt "Near-Term Outlook" (30–90D), Eyebrow "CONDITIONS SCORE". Signal-Badge zeigt keine BUY/SELL-Signale mehr, sondern kontextuelle Labels ("DEEPLY OVERSOLD", "NEUTRAL CONDITIONS", "OVERHEATED" etc.) mit neutralen/graduellen Farben; Warning-Text: "CONTEXTUAL ONLY — THE ARC INDEX IS THE PRIMARY SIGNAL". Cycle Overview `tactical_signal` aus analyzer.py nutzt phasenbeschreibende Texte (z. B. "New Cycle Underway", "Late Cycle Caution", "Relief Rally Possible", "Historical Buy Zone") statt Handlungsaufforderungen ("BUY AGGRESSIVELY", "REDUCE" etc.).
- **Loading Screen Logo Fix**: window.LOGO_DATA_URL wird im <head> gesetzt; der Loading-Screen nutzt load-logo-img, dessen src per Inline-Script auf window.LOGO_DATA_URL gesetzt wird. Logo sofort sichtbar ohne /static/logo.
- **Fix #86**: _setCyclePhaseTag colMap vollständig — alle 12 Phasen mit Farben. **Fix #87**: updateShortTermContext Fallback Phase aus arcSummary.phase_context (SST). **Fix #88**: analyzer.py Phase Priority — days_since_top<60 nur wenn drawdown>-15%.
- **Index Syntax Fix**: JavaScript SyntaxError `Unexpected identifier 'plugins'` in index.html (ARC History Chart config) behoben, indem der `plugins`-Block korrekt als Property im Chart-Konfig-Objekt eingebettet wurde.

## Frühere Sessions
- **Phase-coherent decision engine (main.py)**: Position/Allocation/Confidence in get_arc_summary() leiten sich primär aus der **Phase** (analyzer.get_short_term_context) ab. Phase-Gruppen: BEAR_PHASES, BULL_PHASES, ACCUMULATION_PHASES, LATE_BULL_PHASES. Bear → "WAIT — Bear Market", expected_range bear_wait; /api/historical-returns phase_group. Response: phase_context, phase_group.
- **ARC display stretching**: scoring.arc_display_score(arc_raw, k=1.5) for UI only; /api/arc-summary arc_display, /api/cycle/combined arc_display; backtest score_display; index Hero/Gauge/Banner/Chart use arc_display/score_display; Data Inspector raw + display; phaseOf/scoreColor 25/45/65.
- ✅ **Phase logic from cycle_anchor only**: analyzer.get_short_term_context() phase no longer derived from ARC; phase from days_since_top, days_since_bottom, drawdown_from_top only. Tactical per phase (Late Bull/Early Bear/Mid Bear/Late Bear/Accumulation/Deep Accumulation/Early Bull/Mid Bull).
- ✅ ARC Formula Unification: scoring.compute_arc_score() (ma*0.35 + dd*0.25 + liq*0.25 + fg*0.15), backtest_engine same weights + fg_to_score, /api/arc-summary uses compute_arc_score()
- ✅ **ARC v2**: Momentum from backtest: scoring.compute_arc_momentum(arc_history, days=30); /api/arc-summary exposes arc_momentum (value, label, direction), arc_momentum_30d, arc_momentum_label; percentile from analyzer.
- ✅ **Rescaling reverted**: Raw ARC range (empirical ~22-78). compute_arc_score() returns clamp(arc); no rescale_arc. backtest_engine uses clamp only. Expected range and UI zones (phaseOf, chart bands, hr-grid) calibrated to raw range: bands <25, <35, <45, <55, <65, >=65 (expected range); phaseOf <30 Low, <50 Moderate, <65 Elevated, >=65 High; chart zones 0-25, 25-40, 40-60, 60-70, 70-100.
- ✅ **Short Term Engine v2**: scoring.compute_short_term_score() (RSI 20%, MVRV 20%, Funding 15%, F&G 15%, 50D MA 15%, Puell 15%); signal labels STRONG BUY/BUY/CAUTIOUS LONG/NEUTRAL/REDUCE/SELL. main.py: short_term_scores in cache; /api/short-term endpoint; /api/cycle/btc short_term_v2. index.html: fetch /api/short-term, S.shortTerm, 6 component bars (no Power Law/Pi Cycle), stBarColor <35/<65/>=65.
- ✅ **Short Term Card Visual Redesign** (index.html): Card header "SHORT TERM SIGNALS" + "30-90D"; score block large score (48–56px, DM Mono, color by score), signal badge; tactical banner 11px #6b7280; "COMPONENT BREAKDOWN"; 6 rows label 80px, bar width=score%, track #1a2332 6px, context labels per component; no backend changes.
- ✅ **Expected Range zone-specific**: compute_high_risk_drawdown in historical_returns.py; _get_expected_range(arc, fwd, dd) reduce 50-65 / drawdown 65+; UI by type (forward_return / reduce / drawdown).
- ✅ **Cycle Overview Bug Fix**: updateShortTermContext() no longer early-returns when S.shortTerm.signal exists; _setCyclePhaseTag() always called so CYCLE PHASE, ST SCORE, TACTICAL (cp-*) in Cycle Overview are filled; Short Term Card (st-score-val, st-tactical etc.) only skipped when S.shortTerm.signal present.
- ✅ **Historical Returns Performance**: Backtest + hist_returns/fwd_returns/high_risk_drawdown cached in refresh_cache(); /api/backtest, /api/historical-returns, /api/arc-forward-returns read from CACHE; get_arc_summary and snapshot use CACHE; backtest block in own try/except. Beim API-Startup (`lifespan`) wird die Datei `/tmp/backtest_cache.json` explizit gelöscht (mit Logging/Warnung bei Fehler), sodass der Backtest-Cache bei jedem Deploy/Restart frisch neu berechnet wird.
- ✅ **Historical Returns zone-crossing**: compute_historical_returns() and compute_high_risk_drawdown() use zone-crossing entry only (entry when ARC crosses from outside zone into zone; 12M forward return per entry; extreme zone drawdown from peak after entry).
- ✅ **ARC v3**: fg_to_score() non-linear; drawdown top cap 90; compute_arc_score() extreme boosts; backtest cache cleared at startup.
- ✅ **Phase label + HR zones**: Phase from cycle_anchor only (analyzer.get_short_term_context): days_since_top, days_since_bottom, drawdown_from_top; no ARC-derived phase. Tactical per phase (Late Bull REDUCE, Early Bear REDUCE/ST ONLY, Mid Bear CAUTIOUS LONG, Late Bear ACCUMULATE SLOWLY, Accumulation/Deep Accumulation BUY/STRONG BUY, Early/Mid Bull BUY/HOLD DIPS). main.py /api/historical-returns: elevated reduce, extreme drawdown. index.html: Elevated REDUCE, Extreme drawdown.
- ✅ **Cycle Anchor Bear-Phase**: compute_cycle_anchor() phase-aware (today >= TENTATIVE_CYCLE_TOP → BEAR), cycle_position_percent from bear_progress/bull_progress; return current_phase, phase_label, phase_description, bear_progress_percent. compute_cycle_anchor() phase-aware (today >= TENTATIVE_CYCLE_TOP → BEAR), cycle_position_percent from bear_progress/bull_progress; return current_phase, phase_label, phase_description, bear_progress_percent.
- ✅ FIX 1: /api/arc-summary Endpoint ergänzt
- ✅ FIX 2: /api/prices mit ATH + Dominanz (Kraken-basiert)
- ✅ FIX 3: backtest_engine.py auf Kraken OHLC umgestellt (CoinGecko-Reste entfernt)
- ✅ FIX 4: index.html ATH/Dominanz aus /api/prices (kein CoinGecko mehr)
- ✅ FIX 5: index.html backtest + liquidity-regime in Promise.allSettled + liquidity-components
- ✅ FIX 6: scoring.py short_term dict in compute_btc_score()
- ✅ FIX 37: backend/Dockerfile — eine Datei, CMD mit $PORT, workers=1; Duplikat entfernt
- ✅ FIX 38: fetcher.py Funding Rates OKX (Bybit/Binance 403 auf Railway); fetch_funding_rates mit if-blocks
- ✅ Deployed auf Railway, getestet — Dashboard live bei Score 30/100

## Nächste Schritte
- [ ] X Content für AlphaCycle erstellen
- [ ] Paid SaaS Funnel planen



## Architecture Lock (NEVER change without architect approval)
ARC Formula (unified, research-validated): ma_200w*0.35 + drawdown*0.25 + liquidity*0.25 + fear_greed*0.15
Use fg_to_score(fear_greed) for F&G input. Same formula in scoring.compute_arc_score(), backtest_engine, and /api/arc-summary.
DO NOT modify weights. DO NOT add scoring components.
**ARC output**: compute_arc_score() returns clamp(arc) — raw ARC range (empirical ~22-78). No rescaling. Momentum from backtest via scoring.compute_arc_momentum(arc_history, days=30).
**ARC display (UI only)**: arc_display_score(arc_raw, k=1.2) in scoring.py — k=1.2 optimal (verhindert 0-Werte bei Extrempunkten). Intern (compute_arc_score/Backtest-Formel/Momentum) wird weiter mit dem **rohen ARC** gearbeitet; alle sichtbaren Zonen/Labels im UI (Hero, Phase Banner, Historical Returns, Zone History, Expected Range, Snapshots) nutzen jedoch konsequent den **Display-Score**. Raw 25->~15.6, 50->50, 75->~84.4. Zone-Grenzen im UI: Deep Value 0–29, Accumulation 30–39, Expansion 40–59, Risk Rising 60–69, Euphoria 70–100 (Display-Skala).

## Permanent Fixes (never revert)
1. main.py: All Unicode removed from comments AND string literals
2. main.py: CycleAnalyzer imported + /api/analyzer endpoint active
3. main.py: /api/arc-summary endpoint active
4. fetcher.py: Kraken primary price source (Binance blocked Railway US-West)
5. scoring.py: drawdown_score() returns 50.0 if len(prices) < 10
6. index.html: BACKEND_URL = https://alphacycle-production.up.railway.app
7. index.html: Promise.allSettled (NOT Promise.all)
8. index.html: phaseOf() 5-Zonen-System: <30 Deep Value, 30-40 Accumulation, 40-60 Expansion, 60-70 Risk Rising, >=70 Euphoria. scoreColor/Phase Banner/Hero/Gauge nutzen diese Zonen und Farben (#00DC78, #00B4D8, #58A6FF, #FF9500, #FF3B3B).
9. index.html: S.btcShortTerm = btcC?.short_term || null (after btcComponents)
10. index.html: S.ethComponents = ethC?.components || null (after btcShortTerm)
11. index.html: S.btcScore guard: only use API value if btcC.score > 0
12. main.py: short_term exposed in /api/cycle/btc response
13. main.py: /api/arc-summary endpoint active
14. main.py: BTC/ETH ATH computed from Kraken price history (max of btc_prices)
15. backtest_engine.py: Uses Kraken OHLC (not CoinGecko)
16. index.html: CoinGecko direct calls removed — all data via Railway backend
17. index.html: updatePhaseBanner() uses phaseOf() only — analyzerPhase override removed
18. index.html: hero card has single risk label (btc-tag removed, hero-risk-label kept)
19. index.html: change_24h computed from last 2 history points (Kraken has no 24h change)
20. index.html: /api/backtest and /api/liquidity-regime fetched in Promise.allSettled
21. scoring.py: short_term dict in compute_btc_score() return (rsi, funding, mvrv, power_law, pi_cycle, puell)
22. main.py: arc-summary components.liquidity nutzt macro_liq (nicht liquidity)
23. scoring.py: macro_liq uses 52w window + pct*2.5 amplification (not plain trend_score for WALCL)
24. index.html: Data Inspector panel at bottom (before footer), SHOW/HIDE toggle, renders from S.*; values 0/null orange, 50 default yellow
25. index.html: Data Inspector ARC Summary Liquidity — numeric from S.arcSummary?.components?.liquidity (or .score if object); never display [object Object]
26. main.py: arc-summary regime/decision fallbacks: regime = mac.get("regime","NEUTRAL") or "NEUTRAL", decision = com.get("signal","HOLD") or "HOLD"
27. fetcher.py: merge() BTC/ETH market_cap fallback when 0 — use price * 19_700_000 (approx circulating supply)
28. index.html: /api/arc-summary in Promise.allSettled, S.arcSummary stored; Data Inspector uses S.arcSummary for Regime, Decision, Confidence
29. index.html: Data Inspector all scores rounded to 1 decimal (roundScore / Math.round(x*10)/10) — no floating point display (e.g. 34.135000000005)
30. fetcher.py: after merge(), if gdata.btc_dominance == 50.0 and btc_market.market_cap + total_market_cap > 0, set gdata["btc_dominance"] = round(btc_mc/total_mc*100, 1)
31. index.html: Data Inspector Funding Rate — when 0 or null show "N/A (Binance blocked)" instead of "0.0000%"
32. scoring.py: compute_combined() returns signal + confidence; compute_macro_score() returns regime (EXPANSION/NEUTRAL/CONTRACTION)
33. index.html: Data Inspector ARC Score = Math.round((S.combined ?? 50) * 10) / 10; Funding formatter fmtFunding → "N/A" when 0/null
34. fetcher.py: Funding Rates von Binance auf Bybit umgestellt (Binance Futures auf Railway blockiert)
35. index.html: Data Inspector Liquidity Regime/ARC Summary — liq.liquidity_regime und liq.liquidity_score (NICHT liq.regime / liq.score)
36. liquidity_engine.py: bond_score aus absolutem 10Y-Yield-Niveau berechnen, nicht aus trend_score (Bug: us10y_trend=0 → 100)
37. backend/Dockerfile: Nur eine Dockerfile im backend/ (keine Datei mit Leerzeichen); CMD mit $PORT (nicht hardcoded 8000)
38. fetcher.py: Funding Rates von OKX (Binance Futures und Bybit 403 auf Railway) — fetch_funding_rates() nutzt okx.com/api/v5/public/funding-rate
39. fetcher.py: Global data (btc_dominance, total_market_cap) via CoinCap — CoinGecko /global gibt 429
40. index.html: FRED-Label dynamisch — src-fred je nach S.walclCurrent: FRED oder FRED (synthetic fallback) + class status-src / warn
41. fetcher.py: btc_dominance hardcoded 55.0, total_market_cap 0 — alle externen APIs (CoinGecko 429, CoinCap/Bybit/Binance) auf Railway US-West blockiert. index.html: Data Inspector ohne diRow BTC Dominance / Total Market Cap / BTC Dominance %
42. backtest_engine.py: Paginated Kraken OHLC (max 720/request), ARC = ma_200w*0.35 + drawdown*0.35 + fg(50)*0.15 + liq(50)*0.15. Return {date, price, score}. index.html: ARC History Chart (arc-history-chart) mit Chart.js, S.backtest, Risk-Zonen als fill, Placeholder "Lade historische Daten...".
43. backtest_engine.py: File cache /tmp/backtest_cache.json; einmal 10y laden, taeglich 1-2 fehlende Tage nachladen.
44. backtest_engine.py: WINDOW_200W=1400, HTTP_TIMEOUT=60, Cache min 2000, Fetch 5200d, Abbruch len(candles)<10. index.html Chart UX: yPrice dynamisch skaliert (validPrices 0.88/1.08), Tooltip nur ARC Index + BTC Price.
45. fetcher.py: CoinGecko fetch_market_data aus fetch_all() entfernt (429 auf Railway). asyncio.gather nur noch 11 Aufrufe (0: Kraken BTC/ETH prices+ticker, 4: F&G, 5: TVL, 6: stable, 7: WALCL, 8: DGS10, 9: global_data, 10: funding). btc_cg/eth_cg = leere Fallback-Dicts. Spart ~3s pro Refresh.
46. backtest_engine.py: _fetch_btc_history() since=1381363200 (2013-10-10, Kraken BTC live); bei Kraken OHLC error/kein result Logging; _load_or_build_cache() Exception loggen statt pass.
47. fetcher.py: FRED Net Liquidity (WALCL - WTREGEN - RRPONTSYD). fetch_all() gather 13 Aufrufe: 11/12 fetch_fred_series("WTREGEN") und ("RRPONTSYD"). _compute_net_liquidity(); return net_liq_series, tga_series, rrp_series.
48. scoring.py: macro_liq aus Net Liquidity (net_liq_values). compute_btc_score(net_liq_values=None); 52w Fenster, pct*2.0; Fallback WALCL (pct*2.5). main.py: net_liq_series an compute_btc_score übergeben (data.get("net_liq_series", []) im Cache-Refresh).
49. backtest_engine.py: Net Liquidity im Backtest. _fetch_fred(series_id) lädt WALCL/WTREGEN/RRPONTSYD ab 2013-01-01; net_liq_by_date = WALCL - TGA - RRP; _get_net_liq_score(date_str, net_liq_by_date) für 52w-Trend (50 - pct*2.0). macro_liq pro Tag dynamisch, Fallback 50.0.
50. backtest_engine.py: Kraken OHLC weekly (interval=10080) — Daily max 720 Tage API-Grenze. 720 Wochen = ~13.8 Jahre. WINDOW_200W=200 (200 wöchentliche Punkte = 200-Wochen MA). since=1381363200 (2013-10-10). Cache min 400 Einträge. Ergebnis ~520 ARC-Punkte = ~10 Jahre Chart ab ~2014.
51. index.html: Data Inspector nach WALCL-Zeile: Net Liquidity (S.arcSummary?.components?.net_liq, $XB), TGA (S.arcSummary?.components?.tga, $XB), Macro Liq Score (S.arcSummary?.components?.liquidity, roundScore).
52. fetcher.py: fetch_fred_series() Logging (FRED series_id: len pts). WTREGEN/RRPONTSYD mit start="2015-01-01". main.py /api/arc-summary: components.net_liq + components.tga aus raw (net_liq_series/tga_series letzter Wert) fuer Data Inspector.
53. **5-Zonen UI (index.html)**: phaseOf(score) mit Grenzen 30/40/60/70 → Deep Value, Accumulation, Expansion, Risk Rising, Euphoria. scoreColor, phaseIcon/phaseDesc, Phase Banner, Hero Risk Label, Gauge-Farben für alle 5 Zonen. Cycle Phase Guide (hero-zones) und Historical ARC Returns (hr-grid) 5 Zonen mit Labels/Farben. ARC History Chart zoneLabels-Plugin und getZoneLabelByArc/getHistReturnForArc auf 5 Zonen (deep_value … euphoria).
54. **5-Zonen API (main.py)**: get_zone_name(arc_score) liefert Zone-Name nach gleichen Grenzen; /api/arc-summary Response enthaelt zone_name.
55. **5-Zonen historical_returns.py**: 5 Zonen deep_value (0–30), accumulation (30–40), expansion (40–60), risk_rising (60–70), euphoria (70–100); zone_meta mit zone_name; compute_high_risk_drawdown Euphoria-Eintritt bei arc >= 70.
56. **5-Zonen backtest_engine.py**: ZONES = [(0,29),(30,39),(40,59),(60,69),(70,100)], ZONE_NAMES. /api/historical-returns Keys risk_rising, euphoria (display_mode reduce/drawdown).
57. backtest_engine.py: F&G im Backtest: _fetch_fg_history() (limit=0, alle Daten ab 2018), Mapping {date_str: value}. _rsi_to_fg() als RSI-Proxy für Perioden ohne echte F&G-Werte (Aug 2017–Feb 2018). In run_backtest() pro Tag: fear_greed = fg_history[date] oder _rsi_to_fg(prices_so_far); ARC-Gewicht weiterhin 15%.
58. index.html: ARC History Chart Export (PNG). Button „↓ EXPORT PNG“ im ARC History Header (neben 1Y/10Y Toggle und RESET). exportArcChart(): 1200x675 Canvas, Hintergrund #020510, Chart-Canvas skaliert und mittig, kleine „alphacycle.app“-Signatur unten rechts; Download als alphacycle-arc-YYYY-MM-DD.png; Button im Monospace-Style (DM Mono) an Dashboard-Design angepasst. Zusätzlicher Button „SHARE“ erzeugt via shareArcChart() ein 1200x800 PNG mit Branding-Strip: oben der ARC-Chart (1200x650), darunter dunkler Strip mit Trennlinie, links „AlphaCycle“ (Brand-Farbe, 24px bold) + „alphacycle.app“ (Grau), mittig „ARC [Score]/100 · [Zone] · [Phase]“ in weißer Monospace-Schrift, rechts Datum (YYYY-MM-DD) + „Not financial advice“. Dateiname: alphacycle-[YYYY-MM-DD].png; während des Exports zeigt der SHARE-Button „EXPORTING…“ und wechselt danach zurück zu „SHARE“.
59. main.py: Daily Snapshot System. /api/snapshot/today speichert aktuellen ARC Snapshot in /tmp/arc_snapshots.json (date, arc, btc_price, regime, liquidity, fear_greed, decision, confidence) und gibt ihn zurück. /api/snapshots liefert alle Snapshots. Nach erfolgreichem Cache-Refresh wird _save_today_snapshot() automatisch aufgerufen.
60. index.html: Mobile Responsive Dashboard. @media (max-width: 768px): dashboard/cards/scores/metrics auf 1 Spalte, kleinere Hero-Padding, ARC-Chart-Container für Mobile. ARC Chart (Chart.js) mit maintainAspectRatio: false. Boot-Screen Text „CONNECTING TO KRAKEN…“ (statt COINGECKO).
61. index.html: ARC Chart Resize-Hotfix. Fester Container #arc-chart-wrap (Desktop: height 420px, width 100%), Canvas #arc-history-chart absolut (width/height 100%). Auf Mobile (max-width:768px) #arc-chart-wrap height 280px. In Kombination mit responsive:true + maintainAspectRatio:false verhindert dies unendliches Wachstum beim Scroll/Resize.
62. index.html: Hero Gauge + Liquidity Fix. Hero-Gauge nutzt kombinierten ARC Score (S.combined ?? S.arcSummary?.arc_score ?? S.btcScore) für Farbe, Gauge-Animation und Wert. BTC Liquidity-Component-Bar liest primär S.arcSummary?.components?.liquidity, dann btcComponents.macro_liq (.score oder Wert), fallback 50; kein harter 50er-Default mehr bei vorhandenen Net-Liq-Daten.
63. index.html: ARC History Cycle Marker. Hardcodierte CYCLE_MARKERS-Liste mit Top-/Bottom-Daten (2017-12-17, 2021-11-10, 2018-12-15, 2022-11-21). Chart.js inline Plugin `cycleMarkers` im ARC History Chart (options.plugins.cycleMarkers.afterDraw) zeichnet Dreiecksmarker auf der BTC-Preisachse (rot für Tops, grün für Bottoms) und Label „Cycle Top“ / „Cycle Bottom“ direkt im Chart; Marker-Liste kann später erweitert werden.
64. index.html: AlphaCycle Logo Integration. Favicon im <head> zeigt auf `/static/logo.png` (PNG). Nav-Bar Logo nutzt `<img src="/static/logo.png" alt="AlphaCycle" style="width:32px;height:32px;border-radius:6px;object-fit:contain;">` anstelle des generischen "α"-Marks; erwarteter Auslieferungspfad über backend/static/logo.png auf Railway.
65. ARC Formula Unification: Single formula ma_200w*0.35 + drawdown*0.25 + liquidity*0.25 + fear_greed*0.15. scoring.compute_arc_score() (same liquidity logic as compute_btc_score; compute_btc_score unchanged). backtest_engine: fg_to_score(fear_greed), weights ma*0.35 + dd*0.25 + macro_liq*0.25 + fg*0.15. main.py /api/arc-summary: arc_score from compute_arc_score(), not combined_score.
66. Cycle Anchor Cleanup: TENTATIVE_CYCLE_TOP = date(2025, 10, 6) (BTC ATH ~$126,200) in cycle_anchor.py only. main/analyzer import from cycle_anchor. API returns cycle_top_date (isoformat) and cycle_top_confirmed: False.
67. **ARC raw range**: compute_arc_score() returns clamp(arc); no rescale_arc. Raw ARC empirical range ~22-78. Weights unchanged.
68. **ARC momentum layer**: scoring.compute_arc_momentum(arc_history, days=30) returns {value, label, direction}. /api/arc-summary: arc_history from backtest; arc_momentum = full dict; arc_momentum_30d = momentum["value"]; arc_momentum_label = momentum["label"]; arc_percentile/arc_percentile_label from analyzer.
69. **Cycle Anchor Bear-Phase**: compute_cycle_anchor() if today >= TENTATIVE_CYCLE_TOP then current_phase=BEAR, cycle_position_percent from bear_progress; else BULL from bull_progress. Return: current_phase, phase_label, phase_description, bear_progress_percent (0 in BULL).
70. **Backtest raw ARC**: backtest_engine.py no rescale_arc; arc = max(0, min(100, arc)) only. /api/backtest results use raw ARC.
71. **Expected Range (raw ARC)**: main.py _get_expected_range() fixed lookup for raw ARC: bands <25, <35, <45, <55, <65, >=65; avg_12m cap 300%.
72. **UI zones raw ARC**: index.html phaseOf 5 Zonen: <30 Deep Value, 30-40 Accumulation, 40-60 Expansion, 60-70 Risk Rising, >=70 Euphoria. ARC History Chart risk bands 0-30, 30-40, 40-60, 60-70, 70-100. Hero/Cycle Guide/Historical Returns 5 Zonen mit obigen Farben. historical_returns API: zones deep_value, accumulation, expansion, risk_rising, euphoria mit zone_name.
73. **5-Zonen Backend**: main.py get_zone_name(arc_score) liefert Deep Value/Accumulation/Expansion/Risk Rising/Euphoria; /api/arc-summary enthaelt zone_name. historical_returns.py: 5 Zonen (0-29, 30-39, 40-59, 60-69, 70-100), zone_name pro Zone; compute_high_risk_drawdown Euphoria-Zone (prev < 70, curr >= 70). backtest_engine.py: ZONES = [(0,29),(30,39),(40,59),(60,69),(70,100)], ZONE_NAMES. /api/historical-returns display_mode reduce fuer risk_rising, drawdown fuer euphoria.
74. **Short Term Engine v2**: scoring.compute_short_term_score() (prices_daily, fear_greed, funding_data, indicators, walcl_values, net_liq_values). Components: RSI 20%, MVRV 20%, Funding 15%, Fear&Greed 15%, 50D MA 15%, Puell 15%. Signal labels by score. main.py: short_term_scores in cache; GET /api/short-term; /api/cycle/btc short_term_v2. index.html: fetch /api/short-term, S.shortTerm; Short Term card 6 bars (RSI, MVRV, Funding, Fear & Greed, 50D MA, Puell), no Power Law/Pi Cycle; bar color <35 green, <65 yellow, >=65 red.
75. **Short Term Card Visual Redesign** (index.html only): Card title "SHORT TERM SIGNALS" | "30-90D"; score block with large number (48-56px DM Mono, color by score), signal badge; banner 11px #6b7280; "COMPONENT BREAKDOWN"; 6 rows with label 80px, bar width=score%, track #1a2332 6px, context labels (RSI/MVRV/Funding/F&G/50D MA/Puell per spec). No backend changes.
76. **Expected Range zone-specific**: historical_returns.compute_high_risk_drawdown(backtest_data) for ARC >= 65 (max drawdown from peak after zone entry, 52w window). main.py _get_expected_range(arc, fwd, high_risk_drawdown): arc < 50 forward_return bands; 50-65 type "reduce" label "REDUCE — DO NOT BUY"; arc >= 65 type "drawdown" with avg/max/min_drawdown. All _get_expected_range() call sites pass compute_high_risk_drawdown(results). index.html: expected_range by type — forward_return green +%; reduce "REDUCE — DO NOT BUY" #f97316; drawdown "AVG -X% FROM PEAK" #ef4444 + "Worst case: -Y%" sub line.
77. **Cycle Overview fix**: index.html updateShortTermContext() must not early-return when S.shortTerm.signal exists. _setCyclePhaseTag() always called (with fallback when !ctx) so Cycle Overview card (ca-cycle-phase-tag, cp-st-score, cp-tactical, cp-upside, cp-downside) is filled. Short Term Card (st-score-val, st-tactical, st-upside-pct etc.) only filled when S.shortTerm.signal is absent; when present, renderShortTerm() owns that card.
78. **Historical Returns cache**: After refresh_cache() CACHE.update(), a try/except block runs run_backtest() and stores backtest_results, hist_returns, fwd_returns, high_risk_drawdown in CACHE. /api/backtest, /api/historical-returns, /api/arc-forward-returns return from CACHE when present; get_arc_summary and /api/snapshot/today use CACHE for results/fwd/dd_data. Backtest block must not crash main cache refresh.
79. **ARC v3**: scoring.py fg_to_score() non-linear mapping (extremes amplified for cycle tops/bottoms); drawdown_score() returns 90.0 when dd>=0 (ATH); compute_arc_score() adds extreme condition boosts (ma>78 and fg>82 +7, ma>72 and fg>75 +3; dd<18 and fg<15 -7, dd<25 and fg<20 -3) before clamp. Weights unchanged. main.py lifespan deletes /tmp/backtest_cache.json at startup so backtest rebuilds with new scoring.
80. **Phase from cycle_anchor only**: analyzer.py get_short_term_context() derives phase ONLY from cycle_anchor (days_since_top, days_since_bottom, drawdown_from_top). ARC is risk thermometer only, NOT phase indicator. Priority: (1) days_since_top<60 Late Bull, (2) days_since_top<180 and drawdown>−20% Early Bear, (3) days_since_top<365 and drawdown>−40% Mid Bear, (4) days_since_top<365 and drawdown>−55% Late Bear, (5) days_since_top<365 and drawdown≤−55% Deep Bear, (6) days_since_top≥365 and arc>35 Accumulation, (7) days_since_top≥365 and arc≤35 Deep Accumulation, (8) days_since_bottom<180 Early Bull, (9) days_since_bottom<400 Mid Bull, (10) else Late Bull. phase_desc and tactical_signal/tactical_color per phase. main.py /api/historical-returns: elevated display_mode reduce, extreme drawdown from CACHE. index.html: Elevated REDUCE/DO NOT BUY, Extreme drawdown.
81. **Historical Returns zone-crossing entry**: historical_returns.compute_historical_returns() counts an entry ONLY when ARC crosses FROM OUTSIDE a zone INTO the zone (previous week not in zone, current week in zone). Per zone: entry_count, avg_12m (12-month forward return), win_rate_12m; avg_3m, avg_6m, min_12m, max_12m for compatibility. compute_high_risk_drawdown() uses same zone-crossing logic for extreme (prev < 65, curr >= 65); drawdown from peak after entry within 52 weeks. Expected entry counts: low <10, moderate 10–20, elevated 5–15, extreme 3–8.
82. **ARC display stretching**: scoring.arc_display_score(arc_raw, k=1.5) — sigmoid stretch for UI only. NEVER in compute_arc_score() or compute_btc_score(). Only at output: /api/arc-summary arc_display, /api/cycle/combined arc_display; backtest_engine score_display; index.html Hero/Gauge/Banner/Chart use arc_display or score_display; Data Inspector shows "ARC Score (raw)" and "ARC Score (display)". UI zone thresholds: phaseOf/scoreColor <25 Low, 25–45 Moderate, 45–65 Elevated, >65 High Risk.
83. **Phase-coherent decision engine**: get_arc_summary() position/allocation/confidence from phase first (analyzer.get_short_term_context phase_label). Phase groups: BEAR_PHASES, BULL_PHASES, ACCUMULATION_PHASES, LATE_BULL_PHASES (main.py module-level). Bear → WAIT — Bear Market, allocation 20–40% or 0–20%, confidence Low, expected_range bear_wait. Late Bull → REDUCE, 20–40% or 0–20%, Low-Moderate. Accumulation/Bull by ARC thresholds. Fallback: unknown phase → existing ARC-only logic. Response: phase_context, phase_group (bear|bull|accumulation|late_bull|unknown). _get_expected_range(arc, fwd, dd, phase): if phase in BEAR_PHASES return bear_wait. /api/historical-returns adds phase_group (same phase logic). compute_arc_score/compute_btc_score/ARC formula/arc_display_score unchanged.
84. **Phase-coherent UI**: index.html getPhaseGroup() (S.arcSummary.phase_group || from S.analyzerPhase). renderDecision: dec-position color bear = #f59e0b, "WAIT — Bear Market" = #6b7280. Historical ARC Returns always show actual low/moderate/elevated zone stats (avg_12m/win_rate/entries) regardless of phase; only the extreme zone remains styled as drawdown warning. Single Source of Truth fuer Cycle Phase im UI: S.arcSummary.phase_context — sowohl Hero (Alpha Cycle Index) als auch Cycle Overview (_setCyclePhaseTag/updateShortTermContext) nutzen dieses Label; _setCyclePhaseTag() hat konsistente Farbcodes fuer Early/Mid/Late/Deep Bear und Bull/Accumulation Phasen.
85. **BTC Chart High-Low Range**: backtest_engine returns per week high/low (Kraken OHLC c[2], c[3]); cache and results include "high", "low", "price" (close). index.html ARC History Chart: BTC as High-Low band, BTC Close line thin yellow, BTC Low transparent; cycle markers TOP/BOTTOM use result.high and result.low. ATH band ~$126k visible.
86. **ARC High/Low Engine**: arc_display_score k=1.2 (extrempoint-optimal). drawdown_score_hl(prices, price_override) in scoring; compute_arc_score(weekly_high=None, weekly_low=None) overrides ma_score/dd_score after compute_btc_score when high/low present. Backtest: ma_200w_score from weekly_high, dd_score from drawdown_score_hl(prices_so_far, weekly_low). main.py live: weekly_high=None, weekly_low=None (fallback Close). compute_btc_score() unchanged. Chart uses score_display for ARC line.

## Active Endpoints (Railway)
/health /api/prices /api/cycle/btc /api/cycle/eth /api/cycle/macro
/api/arc-summary /api/cycle/combined /api/history /api/fear-greed
/api/short-term /api/cycle-anchor /api/analyzer /api/backtest /api/liquidity-regime /api/decision

## Frontend Sections (in order) & Layout
1. Hero: ARC Index (btc-card with hero-card class)
2. Decision Engine card
3. Short Term Tactical Layer card
4. Cycle Anchor card
5. Sub-Analysis: ETH Relative Strength + Liquidity Regime
6. Phase Banner, Key Indicators, Live Prices, Cycle Phase Guide
7. Data Inspector (collapsed by default, SHOW/HIDE toggle; auf Mobile max-height ~60vh mit Scroll)

**Mobile & Tablet Layout**: index.html ist für Mobile (<=768px) und Tablet (<=1024px) optimiert. Ticker-Bar auf Mobile zeigt nur BTC/USD, ETH/USD, F&G und BTC CYCLE (ETH/BTC, ETH CYCLE, MACRO via .tick--mobile-hide ausgeblendet). REFRESH-Button hat auf kleinen Screens kompakteres Padding. Hero-Card (AlphaCycle Index) stapelt auf Mobile Gauge und Info untereinander; Factor-Subscores umbrechen in mehrere Zeilen. Decision Engine nutzt auf Mobile ein 2x2-Grid für Position/Allocation/Expected Range/Confidence. Historical ARC Returns (5 Zonen) sind horizontal scrollbar mit „← scroll →“-Hinweis; jede Zone hat eine Mindestbreite, damit die Inhalte lesbar bleiben. Cycle Overview Card stapelt die linke Phase-Spalte und die rechte Timeline-Spalte untereinander. Live Prices (3 Cards) werden auf Mobile vertikal gestapelt. Near-Term-Outlook-Card reduziert auf Mobile Abstände und stapelt Score-Block und Banner untereinander. ARC History Chart-Container: Desktop-Höhe 420px, Mobile 280px; ARC Momentum Chart auf Mobile ~120px hoch. Content-Export „COPY DATA“-Button ist auf Mobile full-width. Data Inspector bleibt standardmäßig eingeklappt, hat aber auf Mobile eine begrenzte Höhe mit Scroll, um Vollbild-Übernahme zu vermeiden.

## Data Sources
Prices: Kraken (primary). CoinGecko fetch_market_data entfernt (429 auf Railway); btc_cg/eth_cg = leere Fallbacks.
Global/dominance: hardcoded 55% (APIs blockiert auf Railway)
Funding: OKX (Binance Futures + Bybit 403 auf Railway)
F&G: Alternative.me
TVL+Stablecoins: DeFiLlama
Fed Balance: FRED (WALCL, DGS10, WTREGEN, RRPONTSYD). Net Liquidity = WALCL - TGA - RRP.
