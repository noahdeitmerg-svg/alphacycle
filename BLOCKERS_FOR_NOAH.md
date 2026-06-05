# Blockers for Noah — erledigen, dann läuft der Verkauf

> Stand 2026-06-05 (Cowork autonome Session). Alles Technische ist gebaut, getestet
> und live gepusht. Diese Liste = nur die Dinge, die **ich nicht ohne dich** machen
> kann (Account-Erstellung, DB-DDL, Secrets). Reihenfolge = Wirkung.

---

## 1. 🔴 Lemon Squeezy aktivieren → Verkauf startet (15–20 Min)
Stripe wartet auf die US-LLC; **Lemon Squeezy (Merchant of Record)** verkauft sofort weltweit ohne LLC und macht die Steuer. Checkout ist im Code schon verdrahtet.

1. Account + Store auf https://lemonsqueezy.com anlegen (Store-Name z. B. „AlphaCycle").
2. Produkt **„AlphaCycle Pro"** anlegen, **Subscription**, 2 Varianten:
   - Monthly **$29**, 7-day free trial
   - Annual **$278** (2 Monate gratis)
3. Checkout-/Buy-URL(s) kopieren und mir geben **oder** in `index.html` eintragen
   (im `<head>`-CONFIG-Block, leer = Stripe-Fallback):
   ```js
   window.LEMON_CHECKOUT_URL = 'https://<store>.lemonsqueezy.com/buy/<variant-id>';        // monthly
   window.LEMON_CHECKOUT_URL_ANNUAL = 'https://<store>.lemonsqueezy.com/buy/<variant-id>'; // annual
   ```
4. **Webhook** in LS einrichten → URL `https://alphacycle-production.up.railway.app/api/lemonsqueezy-webhook`,
   Events: `subscription_created`, `subscription_updated`, `subscription_cancelled`,
   `subscription_expired`, `subscription_payment_success`.
   Signing-Secret kopieren → in **Railway** als Env-Var **`LEMONSQUEEZY_WEBHOOK_SECRET`** setzen.
   → Danach werden zahlende Kunden **automatisch** auf Pro geschaltet (kein manuelles Eingreifen).

## 2. 🟠 Supabase `email_captures`-Tabelle prüfen/anlegen (5 Min)
Die Email-Capture/Waitlist auf der Landing funktioniert (UX), aber der Endpoint
konnte beim Test **nicht in Supabase speichern** (500 → jetzt abgefangen, Lead landet
sonst nur im Server-Log). Ursache: Tabelle/Schema. Bitte im **Supabase SQL Editor**:
```sql
create table if not exists email_captures (
  id bigint generated always as identity primary key,
  email text not null,
  source text,
  arc_score numeric,
  zone text,
  created_at timestamptz default now()
);
-- optional gegen Duplikate:
create unique index if not exists email_captures_email_uniq on email_captures (lower(email));
```
Danach speichert die Waitlist sauber. (DDL kann ich von hier nicht ausführen.)

## 3. 🟠 Instagram + YouTube Accounts anlegen (für Content-Factory)
Die Content-Factory (`content-factory/generate.py`) erzeugt täglich fertige
Regime-Grafiken (IG 1080×1080 + YT 1920×1080) — getestet, funktioniert.
Damit ich Posten/Scheduling verdrahten kann, brauche ich von dir:
1. Instagram **Business/Creator**-Account erstellen.
2. YouTube-Kanal erstellen.
3. IG mit **Meta Business Suite** (oder Buffer/Later) verbinden.
→ Dann hänge ich Generator + offiziellen Scheduler zusammen. **Niemals** Login-Bots
   (genau das hat X gebannt) — nur offizielle APIs + Mensch-im-Loop.

## 4. 🟢 X-Bot sofort hart stoppen (optional, 1 Min)
Schon dauerhaft pausiert (`BOT_PAUSED`, greift bei Reboot/Redeploy). Für sofortige
Wirkung am laufenden Prozess:
```bash
ssh root@95.216.152.31
screen -S xbot -X quit
```

## 5. 🟢 Email-Versand (Nurture) verbinden — wenn Leads kommen
Für „Weekly ARC Regime Brief" + Trial-Nurture: **beehiiv** (gratis bis 2.500 Subs,
0 % Fee) oder Resend. Leads aus `email_captures` exportieren/syncen. Empfehlung &
Funnel-Zahlen in `docs/GTM_STRATEGY.md`.

## 6. ⚪ Stripe (später, niedrigere Gebühren)
US-LLC (Wyoming ~$100 + $60/yr) → Stripe Live → Pro-Preis **$29** → Checkout im Code
von Lemon Squeezy auf Stripe umstellen (eine Config-Zeile). Bis dahin ist LS völlig ok.

---

### Was bereits LIVE und erledigt ist (Cowork)
- X-Bot pausiert + durabler Kill-Switch (Account-Block).
- GTM-/Viability-Recherche → `docs/GTM_STRATEGY.md`.
- Dashboard verkaufsfertig: 5-Card-Kern-Story, schwache Cards reversibel versteckt,
  Preis $29, Deutsch→Englisch, Debug-Logs raus.
- Landing = Sales-Page: Email-Capture, FAQ, Annual-Option, Disclaimer.
- Lemon-Squeezy-Checkout verdrahtet + `/api/lemonsqueezy-webhook` (Auto-Entitlement).
- **Unabhängiger Backtest + Trust-Audit:** Datenintegrität 0 Fehler; alle überstellten
  Landing/Track-Record-Zahlen auf echte Backtest-Daten korrigiert (Cycle-Top $124,8k
  statt $108k, reale ARC/BTC/Returns). Verify-Tool: `backend/scripts/verify_dashboard.py`.
- `/api/subscribe` 500-Bug gefixt + kugelsicher gemacht.
- Content-Factory gebaut + getestet (`content-factory/`).
