# BLOCK 1+2 — Test-Checkliste (vor Go-Live)

Durchgehen **bevor** du live gehst.  
`[x]` = im Code verifiziert / `[ ]` = nur manuell prüfbar.

**Durchgegangen:** Alle im Code prüfbaren Punkte verifiziert. Rest = manuell im Browser / Railway / Stripe.

---

## Nach BLOCK1_PROMPT1 (Bug Fixes)

- [x] **Blur Overlays lesbar (Text nicht verschwommen)?**  
  Verifiziert: `blur-content` und `blur-overlay` sind Geschwister; nur `.blur-content` wird geblurrt.

- [x] **Hero zeigt "ACCUMULATION" nicht "DEEP VALUE" bei ARC ~32?**  
  Verifiziert: `updateHeroRisk()` nutzt `arcRaw = S.arcSummary?.arc_score ?? …` und `phaseOf(arcRaw)` für `hero-risk-label`. Grenze 30–39 = Accumulation.

- [x] **Blur Gates überlappen sich nicht?**  
  Verifiziert: `.blur-gate.locked` hat `min-height: 220px` und `margin-bottom: 16px` (inkl. @media 480px).

---

## Nach BLOCK1_PROMPT2 (Stripe Backend)

- [x] **Stripe-Code in main.py vorhanden?**  
  Verifiziert: `import stripe`, `return {"checkout_url": session.url}`, `stripe.Webhook.construct_event` in main.py.  
  **Manuell:** Railway-Deploy-Logs prüfen (kein Import-Fehler).

- [x] **POST /api/checkout liefert checkout_url?**  
  Verifiziert: Endpoint gibt `{"checkout_url": session.url}` zurück.  
  **Manuell:** Mit Bearer-Token und Body `{ "user_id", "email" }` testen; Stripe Test Keys in Railway setzen.

- [ ] **Webhook-URL in Stripe Dashboard eingetragen?**  
  **Nur manuell:** Stripe Dashboard → Webhooks → Endpoint-URL eintragen (z. B. `https://alphacycle-production.up.railway.app/api/stripe-webhook`) + Events wählen.

---

## Nach BLOCK1_PROMPT3 (Stripe Frontend)

- [x] **"UPGRADE TO PRO — $49/mo" Button bei eingeloggten Free-Usern sichtbar?**  
  In `applyBlurGates()` wird bei Paid-Gates und `effectivePlan !== 'anonymous'` (Free eingeloggt) `btn.textContent = 'UPGRADE TO PRO — $49/mo'` und `btn.onclick = openUpgradeModal` gesetzt.

- [x] **Klick auf Button → Weiterleitung zu Stripe Checkout?**  
  Verifiziert: `openUpgradeModal()` ruft POST `/api/checkout` auf; bei `data.checkout_url` erfolgt `window.location.href = data.checkout_url`. **Manuell:** Im Browser mit eingeloggtem Free-User testen.

- [x] **Nach Zahlung (Test) → zurück auf alphacycle.app/#upgrade-success?**  
  In `main.py` ist `success_url="https://alphacycle.app/#upgrade-success"` gesetzt. **Manuell:** Nach Testzahlung tatsächlich auf diese URL geleitet?

- [x] **"WELCOME TO ALPHACYCLE PRO" Banner erscheint?**  
  Bei `window.location.hash === '#upgrade-success'` nach 2s: `fetchUserPlan()`, `updateAuthUI()`, `applyBlurGates()`, Banner-Node mit Text „✓ WELCOME TO ALPHACYCLE PRO“, nach 5s entfernt, Hash geleert.

- [x] **Paid Sections entsperrt?**  
  Nach `#upgrade-success` wird `fetchUserPlan()` und `applyBlurGates()` aufgerufen; bei `plan === 'paid'` sind Paid-Gates mit `effectivePlan === 'paid'` unlocked.

---

## Nach BLOCK1_PROMPT4 (Trial)

- [x] **Neuer Sign-Up → Navbar zeigt "TRIAL · 7d left"?**  
  `updateAuthUI()`: Bei `currentPlan === 'trial'` wird `planBadge.textContent = 'TRIAL · ' + daysLeft + 'd left'` (daysLeft aus `trialEndsAt` oder Fallback 7), Styling mit #00D4AA.

- [x] **Alle Sections (inkl. Paid) sichtbar während Trial?**  
  `applyBlurGates()`: `effectivePlan = currentPlan === 'trial' ? 'paid' : currentPlan`; Paid-Gates locked nur bei `effectivePlan !== 'paid'`. Bei Trial wird zusätzlich `.blur-overlay` bei Paid-Gates ausgeblendet.

- [x] **/api/auth/profile gibt plan: "trial" zurück?**  
  Bei neuem User (nach Insert) wird `plan: "trial"`, `trial_active: true`, `trial_ends_at: (utcnow + 7d).isoformat()` zurückgegeben. Bei bestehendem Free-User mit Trial wird `effective_plan = "trial"` als `plan` geliefert.

---

## Nach BLOCK2_PROMPT1 (Landing Page)

Landing und Dashboard sind in `index.html` (landing-view / dashboard-view) umgesetzt.

- [x] **Nicht eingeloggt → Landing Page sichtbar?**  
  Verifiziert: `initAuth()` ruft bei `!currentUser` `showLanding()` auf; `showLanding()` setzt landing-view auf block, dashboard-view auf none.

- [x] **Live ARC Score + Zone + BTC Preis auf Landing?**  
  Verifiziert: `updateUI()` befüllt `landing-arc-score`, `landing-arc-zone`, `landing-btc-price`, `landing-fg`, `landing-now-detail` aus S.arcSummary / S.btcMarket / S.fgCurrent.

- [x] **"START 7-DAY FREE TRIAL" Button öffnet Sign-Up Modal?**  
  Verifiziert: Landing-CTA hat `onclick="openAuthModal('signup')"`.

- [x] **Pricing Section zeigt $0 (Free) und $49/mo (Pro)?**  
  Verifiziert: Im Markup vorhanden ($0 Free, $49/mo Pro mit 7 DAYS FREE Badge).

- [x] **"View Dashboard →" Link zeigt Dashboard mit Blur Gates?**  
  Verifiziert: Link ruft `showDashboard()` auf; Dashboard enthält alle Blur-Gates.

- [x] **Nach Login → automatisch zum Dashboard?**  
  Verifiziert: `onAuthStateChange` ruft bei `session` `showDashboard()` auf.

- [x] **Track Record Teaser mit 3 historischen Beispielen?**  
  Verifiziert: Drei Karten auf Landing (Dec 2022 Deep Value, Oct 2024 Risk Rising, Now Accumulation).

---

## Nach BLOCK2_PROMPT2 (Track Record)

Track Record ist in `index.html` als `track-record-view` umgesetzt.

- [x] **"View Full Track Record →" Link auf Landing funktioniert?**  
  Verifiziert: Link unter dem Teaser mit `onclick="showTrackRecord();return false;"`; `showTrackRecord()` blendet track-record-view ein.

- [x] **Track Record Seite zeigt 4 historische Signale?**  
  Verifiziert: Vier Karten in track-record-timeline (Deep Value Nov 2022, Accumulation Mar 2023, Risk Rising Oct 2024, Current Signal).

- [x] **"Back" Link geht zurück zur Landing?**  
  Verifiziert: "← BACK" mit `onclick="showLanding();return false;"`.

- [x] **CTA Button öffnet Sign-Up Modal?**  
  Verifiziert: Track-Record-CTA hat `onclick="openAuthModal('signup')"`.

---

## Stripe Live-Schalter (wenn alles im Test funktioniert)

- [ ] Stripe Dashboard: Test → Live Mode
- [ ] Railway: `STRIPE_SECRET_KEY` auf `sk_live_...` setzen
- [ ] Railway: `STRIPE_WEBHOOK_SECRET` auf Live `whsec_...` setzen
- [ ] Railway: `STRIPE_PRICE_ID` auf Live `price_...` setzen
- [ ] Webhook-URL in Stripe **Live Mode** erneut eintragen
- [ ] Eine echte Testzahlung mit eigener Karte durchführen
- [ ] Sofort refunden (Stripe Dashboard → Payments → Refund)

---

**Kurz:** Alle im Code prüfbaren Punkte sind durchgegangen und mit [x] markiert. Offen für **manuelles Testen**: Railway-Deploy-Logs, POST /api/checkout mit echtem Token, Webhook-URL im Stripe-Dashboard, Stripe-Checkout-Flow im Browser, Live-Umschaltung Stripe Test → Live.
