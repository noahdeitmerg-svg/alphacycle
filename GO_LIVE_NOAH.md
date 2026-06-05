# AlphaCycle — Go-Live Checklist (Noah)

Alles Frontend-seitige ist fertig und live. Diese Datei deckt nur die Schritte ab, die deine Keys / dein Auth brauchen. Reihenfolge wie unten abarbeiten.

Geschätzt: ~45–60 Min.

---

## 1. Supabase — Tabellen anlegen (~10 Min)

Behebt den `stored:false`-Fehler bei `/api/subscribe` (Tabelle fehlte).

1. Supabase Dashboard → dein Projekt → **SQL Editor** → **New query**.
2. Folgendes einfügen und **Run**:

```sql
-- Email captures (auch ohne Auth)
CREATE TABLE IF NOT EXISTS email_captures (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    source TEXT DEFAULT 'dashboard',
    arc_score INTEGER,
    zone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    beehiiv_synced BOOLEAN DEFAULT FALSE
);

-- User profiles (verknüpft mit Supabase Auth)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID REFERENCES auth.users(id) PRIMARY KEY,
    email TEXT,
    plan TEXT DEFAULT 'free',
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT DEFAULT 'inactive',
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert log
CREATE TABLE IF NOT EXISTS alert_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    arc_score INTEGER,
    zone_from TEXT,
    zone_to TEXT,
    emails_sent INTEGER DEFAULT 0
);

-- Row Level Security
ALTER TABLE email_captures ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles  ENABLE ROW LEVEL SECURITY;

-- Policies: jeder User darf nur sein eigenes Profil lesen/ändern
CREATE POLICY "Users can read own profile"
  ON user_profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE USING (auth.uid() = id);
```

> Das Backend schreibt mit dem **Service-Role-Key** (umgeht RLS), Reads vom Frontend laufen über die Policies. Beides ist abgedeckt.

3. **Auto-Profil bei Signup** (empfohlen, sonst hat ein neuer User keine `user_profiles`-Zeile):

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email, plan)
  VALUES (NEW.id, NEW.email, 'free')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

---

## 2. Stripe — Produkte, Preise, Webhook (~20 Min)

Mach das zuerst im **Test-Modus** (Toggle oben rechts im Stripe-Dashboard), erst nach erfolgreichem Test auf Live umstellen.

### 2a. Produkt + Preise
1. Stripe → **Products** → **Add product**.
   - Name: `AlphaCycle Pro`
2. Zwei Preise hinzufügen (beide *recurring*):
   - **Monthly** — z. B. $29 / month → kopiere die **Price ID** (`price_...`) = `STRIPE_PRICE_MONTHLY`
   - **Yearly** — z. B. $290 / year → kopiere die **Price ID** = `STRIPE_PRICE_YEARLY`

### 2b. API-Key
3. Stripe → **Developers → API keys** → **Secret key** (`sk_...`) kopieren = `STRIPE_SECRET_KEY`.

### 2c. Webhook
4. Stripe → **Developers → Webhooks** → **Add endpoint**.
   - Endpoint URL: `https://<dein-railway-backend>/api/stripe-webhook`
     *(Railway-Domain unter Railway → Service → Settings → Networking)*
   - Events to send (mindestens):
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
   - Speichern → **Signing secret** (`whsec_...`) kopieren = `STRIPE_WEBHOOK_SECRET`.

---

## 3. Railway — Environment Variables (~5 Min)

Railway → dein Backend-Service → **Variables** → folgende setzen (Werte aus Schritt 2):

| Variable | Wert |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_...` (später `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRICE_MONTHLY` | `price_...` (Monatspreis) |
| `STRIPE_PRICE_YEARLY` | `price_...` (Jahrespreis) |
| `SUPABASE_URL` | `https://<project>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → `service_role` Key |
| `TELEGRAM_BOT_TOKEN` | Bot-Token von @BotFather (für Regime-Alerts) |
| `TELEGRAM_ALERT_CHANNEL_ID` | Kanal-ID/Handle, z. B. `@alphacycle_alerts` (siehe Abschnitt 7) |

> `STRIPE_PRICE_ID` (alt, einzeln) bleibt als Fallback erlaubt, ist aber nicht nötig wenn MONTHLY/YEARLY gesetzt sind. Railway redeployt nach dem Speichern automatisch.

---

## 4. Frontend — Auth & „Go Pro" verdrahten

Das hängt an deinem Auth-System. Was das Backend bereits bereitstellt:

- `POST /api/checkout` — Body: `{ "user_id": "<supabase-uid>", "email": "<email>", "plan": "monthly" | "yearly" }` → Antwort `{ "checkout_url": "..." }` (dahin redirecten).
- `POST /api/create-portal-session` — Body: `{ "user_id": "<supabase-uid>" }` → `{ "portal_url": "..." }` (Abo verwalten/kündigen).
- `POST /api/stripe-webhook` — setzt `user_profiles.plan` automatisch auf `paid`/`free`.

**Zu tun (im Dashboard `app.html`):**
1. Nach Login die Supabase-Session holen → `user_id` + `email`.
2. „Go Pro"-Button → `fetch(API+'/api/checkout', {method:'POST', body: JSON.stringify({user_id, email, plan})})` → `window.location = checkout_url`.
3. Gate-Freischaltung an echten Plan koppeln statt localStorage:
   - In `applyGates()` statt `localStorage.getItem('ac_unlocked')` den eingeloggten Plan prüfen (`plan === 'paid'` oder „user ist eingeloggt", je nachdem ob du nur Signup oder zahlend gaten willst).
   - `unlockPro()` → bei anonymem User dein Signup-Modal öffnen statt direkt freizuschalten.

> Aktuell: Gates entsperren per Klick (localStorage) — funktioniert als Platzhalter, bis Auth dran ist. Nichts ist kaputt, es ist nur noch nicht an echte Accounts gekoppelt.

---

## 5. Test (Test-Modus, ~10 Min)

1. Signup/Login durchspielen → prüfen: `user_profiles`-Zeile entsteht (Supabase Table Editor).
2. „Go Pro" → Stripe-Checkout mit Testkarte `4242 4242 4242 4242`, beliebiges zukünftiges Datum, beliebige CVC.
3. Nach Zahlung: `user_profiles.plan` sollte auf `paid` springen (Webhook). Stripe → Webhooks → Endpoint → letzte Events = `200`.
4. Portal testen: `/api/create-portal-session` → Abo sichtbar/kündbar.
5. Wenn alles grün: Stripe auf **Live** umstellen, Live-Keys in Railway eintragen, Live-Webhook anlegen.

---

## 7. Telegram Regime-Alerts (~10 Min) — NEU, Code ist fertig

Die Alert-Engine ist gebaut (`backend/alerts.py`) und hängt im Refresh-Loop: bei jedem Daten-Refresh vergleicht sie die Live-ARC-Zone mit der zuletzt gemeldeten (aus `alert_log`) und postet bei Wechsel automatisch in einen Telegram-Kanal. Du musst nur den Kanal + Token bereitstellen.

1. **Bot-Token**: in Telegram @BotFather → `/newbot` (oder bestehenden Bot nehmen) → Token = `TELEGRAM_BOT_TOKEN`.
2. **Kanal anlegen**: neuen Telegram-**Kanal** erstellen (öffentlich, z. B. `@alphacycle_alerts`). Pro-User treten später diesem Kanal bei — so brauchst du kein per-User-Management.
3. **Bot als Admin** in den Kanal hinzufügen (mit Recht „Nachrichten posten").
4. In Railway setzen: `TELEGRAM_BOT_TOKEN` und `TELEGRAM_ALERT_CHANNEL_ID` (= `@alphacycle_alerts` oder die numerische ID).
5. Fertig. Beim ersten Refresh setzt die Engine still eine Baseline (kein Spam), danach feuert sie nur bei echten Zonenwechseln. Jeder Alert wird in `alert_log` protokolliert (keine Doppelmeldungen).

> Sind die ENV-Vars nicht gesetzt, überspringt die Engine den Versand sauber — nichts crasht. E-Mail-Alerts sind im Code als Hook vorbereitet (`# TODO(email)`), aber bewusst noch nicht scharf — kommt über den `email_captures`/Beehiiv-Pfad.

**Hinweis:** Aktuell feuert sie bei jedem Zonenwechsel. Wenn ARC nahe einer Grenze pendelt, könnten kurz hintereinander zwei Alerts kommen. Für den Start ok; später kann man eine Hysterese/Mindestabstand einbauen.

---

## 6. Kleinkram

- Legal-Kontaktadressen anlegen/weiterleiten: `privacy@alphacycle.app`, `support@alphacycle.app` (stehen in den Legal Pages).
- Optional: Erfolgs-/Abbruch-Redirects gehen aktuell auf `https://alphacycle.app/app?upgrade=success|cancelled` — falls du eine eigene Dankesseite willst, dort anpassen (`backend/main.py`, `create_checkout`).

---

### Bereits erledigt (Referenz)
ARC-Chart-Marker (TOP/BOTTOM/NOW) + Default 10Y · Pro-Gates (Decision + Near-term) · Formel überall v1.2 (35/30/15/20) · Privacy/Terms/Disclaimer (Brazil/LGPD) · Clean URLs · Stripe-Endpoints + Monthly/Yearly + Portal · Mobile geprüft. Alles live.
