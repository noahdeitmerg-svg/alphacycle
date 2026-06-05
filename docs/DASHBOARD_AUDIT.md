# AlphaCycle Dashboard — Deep Audit & Rebuild Roadmap

> Cowork 2026-06-05. Audit of the **new** `app.html` dashboard + the live engines behind it.
> Locked (never change): ARC formula **35/30/15/20** (v1.2), zones <30/<40/<60/<70, API endpoints, `permanent-fixes.mdc`.
> NOTE: the rebuild prompt quoted 35/25/25/15 — that is the old v1.1 and is NOT applied; v1.2 stands.

## Inventory + Scorecards

Scale 1–10. Status: KEEP / FIX / REBUILD / REMOVE.

### 1. ARC Hero Gauge  — `GET /api/arc-summary` (arc_score, zone_name, btc_price, fear_greed, phase, momentum)
What: the one-number risk index + zone + plain-English "what it means now".
Code 9 (clean, animated, zone-keyed) · Data 9 (live, matches backtest last point) · UI 9 · Sense 9 (the product's core) · Emotion 8 (gauge animates; could add glow pulse).
**GESAMT 9 · KEEP** · small win: count-up already there; add subtle "live" freshness.

### 2. The Composite — 4 components — `components.{ma_200w,drawdown,fear_greed,liquidity}`
What: the four signals + weights that build the score.
Code 8 · Data 9 (live) · UI 8 · Sense 9 (explains the score = trust) · Emotion 6 (static bars).
**GESAMT 8 · KEEP** · win: count-up + reveal animation on bars.

### 3. Decision / Positioning — `position, allocation, confidence_label, expected_range, bottom_formation`
What: posture, allocation range, 12M outlook, confidence.
Code 8 · Data 9 · UI 8 · Sense 8 · Emotion 7.
**GESAMT 8 · FIX (dedup)** — the "12-MONTH OUTLOOK +220%" repeats Track Record's current-zone number. Reframe so it complements, not repeats (show win-rate / "vs all zones" instead, keep +220% owned by Track Record).

### 4. Track Record / Zone Returns — `GET /api/historical-returns`
What: 12M forward returns per zone, current highlighted (YOU ARE HERE).
Code 9 · Data 9 (independently re-backtested) · UI 9 · Sense 10 (the proof / sell argument) · Emotion 9.
**GESAMT 9 · KEEP** — strongest sell card.

### 5. Cycle Clock — `phase_context, days_since_top, cycle_top_date, btc_ath, arc_percentile`
What: time/structure context (phase, days since top, drawdown, percentile).
Code 8 · Data 9 · UI 8 · Sense 8 · Emotion 6.
**GESAMT 8 · KEEP** · win: reveal animation.

### 6. Near-Term (30–90D) — `short_term.{rsi,mvrv,funding,puell,power_law,pi_cycle}`
What: short-term oscillators (contextual only).
Code 7 · Data 8 · UI 8 · Sense 6 (contextual; lower decision value) · Emotion 5.
**GESAMT 7 · KEEP (de-emphasise)** — clearly mark "contextual", keep compact so it doesn't compete with ARC.

### 7. Market Context — eth_btc_signal, seasonality, net_liquidity_data
What: rotation, monthly bias, Fed liquidity.
Code 8 · Data 8 · UI 8 · Sense 7 · Emotion 6.
**GESAMT 7 · KEEP** — good "puzzle pieces", distinct from ARC.

### 8. 10-Year ARC History Chart — `GET /api/backtest`
What: daily ARC + BTC price since 2017 with zone bands.
Code 8 · Data 9 · UI 8 · Sense 9 · Emotion 8 (the visual "wow").
**GESAMT 8 · FIX** — add cycle top/bottom markers + a pulsing "TODAY" dot → biggest wow upgrade, sets us apart.

## Overlap / Dedup Matrix (current zone repeated)
| Info | Hero | Decision | Track Record |
|---|---|---|---|
| Current zone name | ✓ (primary) | ✓ (posture) | ✓ (YOU ARE HERE) |
| +220% 12M | — | ✓ | ✓ (duplicate) |
Resolution: Hero owns the zone *name/score*; Decision owns the *action* (allocation/confidence/win-rate); Track Record owns the *historical returns table*. Remove the duplicate +220% from Decision.

## Information flow (top → bottom) — already logical, keep:
Hero (overview) → Composite (why) → Decision (what to do) → Track Record (proof) → Cycle Clock (where/when) → Near-Term (timing texture) → Context (environment) → 10Y Chart (the long view).

## ROADMAP

**SPRINT 1 — Quick wins (<1h)**
- [ ] Decision card: remove +220% duplicate → show Win Rate + "vs all zones" instead.
- [ ] Scroll reveal (fade+slide) on all cards via IntersectionObserver.
- [ ] Count-up on component + metric values (not just the gauge).
- [ ] Hover lift on cards (translateY(-2px) + border brighten).

**SPRINT 2 — Chart wow (1–3h)**
- [ ] Cycle top/bottom markers on the 10Y chart.
- [ ] Pulsing "TODAY" dot at the current ARC point + tooltip.

**SPRINT 3 — Polish & coherence**
- [ ] Font-size hierarchy pass (one size for card value / label / meta).
- [ ] Loading skeletons instead of "–".
- [ ] Mobile re-verify at 390px.

**SPRINT 4 — Premium / sell**
- [ ] Soft "Pro" teaser on one advanced view (alerts) — dezenter blur, not aggressive.

*Locked elements untouched throughout (ARC formula 35/30/15/20, zones, endpoints).*
