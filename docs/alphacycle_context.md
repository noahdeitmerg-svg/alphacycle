# AlphaCycle — Complete System Context

> **Read this file before making any changes to the repository.**

---

## 1. PROJECT OVERVIEW

AlphaCycle is a live Bitcoin Cycle Intelligence SaaS that classifies the current market regime using a proprietary composite index (ARC Index). It is NOT a trading signal tool — it is a **regime classification system**.

- **Live:** https://alphacycle.app
- **Production:** https://alphacycle-production.up.railway.app
- **GitHub:** https://github.com/noahdeitmerg-svg/alphacycle
- **Stack:** FastAPI + Python 3.12 on Railway, single-file `index.html` (~8800 lines), Supabase Auth/DB, Stripe
- **Owner:** Noah (sole operator, based in Brazil BRT timezone)
- **Languages:** Code + docs in English, internal communication in German

---

## 2. ARC ENGINE

### 2.1 Formula (LOCKED — NEVER CHANGE)

```
ARC = ma_200w × 0.35 + drawdown × 0.25 + liquidity × 0.25 + fear_greed × 0.15
```

- **Weights sum to 1.0** (35 + 25 + 25 + 15)
- All 4 components produce 0–100 scores before weighting
- Output: 0–100 composite score

### 2.2 Components

| Component | Weight | Source | Update Frequency |
|---|---|---|---|
| Trend (200W MA Deviation) | 0.35 | Kraken BTC/USD | Daily |
| Drawdown (ATH Distance) | 0.25 | Kraken BTC/USD | Daily |
| Liquidity (Fed Net Liquidity) | 0.25 | FRED (WALCL, TGA, RRP) | Weekly (Thursday) |
| Sentiment (Fear & Greed) | 0.15 | Alternative.me | Daily |

### 2.3 Zone Boundaries (LOCKED — NEVER CHANGE)

| Zone | Range | Frontend Label |
|---|---|---|
| Deep Value | 0–29 | DEEP VALUE PHASE |
| Accumulation | 30–39 | ACCUMULATION PHASE |
| Expansion | 40–59 | MID CYCLE |
| Risk Rising | 60–69 | ELEVATED RISK |
| Euphoria | 70–100 | EXTREME RISK |

### 2.4 Boundary Implementation

All frontend zone classification uses `< 30 / < 40 / < 60 / < 70` (strict less-than). Functions that must use these boundaries:
- `phaseOf()`, `colorOf()`, `zoneColorForScore()`, `zoneKey`, `renderDecisionInterpretation()`
- Backend: `_phase_label()`, `get_position()`

### 2.5 Data Pipeline

- **CSV:** `backend/data/btc_daily_kraken.csv` (3817 rows, 2013-10-06 to 2024-03-30)
- **Gap Bridge:** CryptoCompare API fills Jan–Mar 2024 gap
- **Live:** Kraken API for daily OHLC from 2024-03-31 onward
- **Backtest:** `run_daily_backtest_full()` produces 3135 daily data points (2017-08-17 → present)

---

## 3. DECISION ENGINE (Positioning Framework)

### 3.1 Backend Positions

`get_position()` in `decision_engine.py`:

```
if a < 30: return "BUY"
if a < 40: return "ACCUMULATE"
if a < 60: return "HOLD"
if a < 70: return "REDUCE"
return "SELL"
```

### 3.2 Frontend Display Mapping

Backend values are mapped to regime language before display:

```javascript
var positionDisplay = {
  'BUY': 'EARLY CYCLE',
  'ACCUMULATE': 'ACCUMULATION PHASE',
  'HOLD': 'MID CYCLE',
  'REDUCE': 'ELEVATED RISK',
  'SELL': 'EXTREME RISK',
  'DEFENSIVE': 'EXTREME RISK',
  'WAIT — Bear Market': 'BEAR PHASE'
}[position] || position;
```

### 3.3 Language Philosophy

AlphaCycle uses **regime-based language**, never action-based:
- ❌ "BUY", "SELL", "SIGNAL", "ENTRY POINT"
- ✅ "PHASE", "REGIME", "ENVIRONMENT", "HISTORICALLY"
- Every user-facing statement uses "historically", "typically" — never "will", "should", "must"

### 3.4 3-Layer Interpretation

The Positioning Framework displays:
1. **Eyebrow:** Zone name + ARC score (e.g. "ACCUMULATION · ARC 35")
2. **Interpretation:** 1-2 sentences about the regime
3. **Typical Positioning:** 3-4 historically-framed bullet points
4. **Disclaimer:** "THIS REFLECTS HOW SIMILAR ENVIRONMENTS BEHAVED HISTORICALLY · NOT A PREDICTION"

---

## 4. DASHBOARD STRUCTURE

### 4.1 Section Order (DOM)

```
gate-hero              (Hero with Orbital Ring)
hero-cta-block         (CTA — anonymous only)
signal-summary         (Zone + ARC score, one line)
HISTORICAL CONTEXT separator
gate-historical-returns (Single dominant zone block)
gate-live-prices       (BTC, ETH, F&G — compact)
gate-decision-engine   (Positioning Framework — linear layout)
gate-cycle-overview    (Cycle Phase, Days Since Bottom/Top)
gate-near-term         (30-90D Outlook)
DEEP ANALYSIS separator
gate-arc-history       (10Y ARC Chart with zoom/pan/auto-fit)
gate-arc-momentum      (ARC Momentum)
gate-zone-history      (Zone History table)
```

### 4.2 Hero — Orbital Design

- **Orbit Ring:** Conic gradient (zone-colored), masked to thin ring via `::before`
- **Score:** `clamp(68px, 10vw, 88px)` centered inside ring
- **Dot:** Positioned on ring at `(score/100) × 360° - 90°`, zone-colored glow
- **Labels:** 5 zone names positioned outside ring (`.ol-dv`, `.ol-ac`, `.ol-ex`, `.ol-rr`, `.ol-eu`)
- **Functions:** `positionOrbitDot(score)`, `highlightOrbitZone(score)`

### 4.3 Blur-Gate System

| Gate | Tier | What it shows |
|---|---|---|
| gate-hero | free | Score, zone, context |
| gate-historical-returns | free | Full HR data visible |
| gate-decision-engine | paid | Positioning Framework |
| gate-cycle-overview | free | Cycle phase data |
| gate-near-term | paid | 30-90D outlook |
| gate-arc-history | paid | 10Y chart |
| gate-zone-history | paid | Zone history table |

### 4.4 Historical Returns

- Uses **confirmed zone periods** from `compute_zone_history()` (~18 entries)
- NOT raw daily crossings (was 257 before fix)
- Forward returns calculated with calendar-day lookup (91/182/365 days)
- Current zone displayed as single dominant block, others as dim reference line

### 4.5 ARC Chart Features

- Zoom/Pan via `chartjs-plugin-zoom@2.0.1` + Hammer.js
- Auto-fit price axis (`autoFitPriceAxis()` with re-entrancy guard)
- 10Y default zoom to last 2 years (730 data points)
- Reset button → 2Y view, Double-click → full 10Y
- Zone band overlays, cycle markers, crosshair

---

## 5. DISTRIBUTION SYSTEM

### 5.1 X Bot (`alphacycle-x-bot/`)

- **Server:** Hetzner VPS (ubuntu-4gb-hel1-2)
- **Stack:** Python 3 + Tweepy v2 + Anthropic Claude API
- **Flow:** scan_tweets() → generate_reply() → post_reply()
- **Limits:** 6/hr, 20/day, 360–1320s random delay before posting
- **Reply Rules:** Max 180 chars, curiosity gap, no self-promotion, no financial advice
- **ARC Context:** Fetches live ARC from `/api/arc-summary` before generating replies

### 5.2 X Content Strategy

- 6 post types: Contrarian Signal, Structural Insight, Contrast, Cycle Pattern, Narrative, Weekly Update
- Posting windows: 10:00 BRT + 20:00 BRT (US Prime Time)
- Reply strategy against Tier-1 analyst list
- Content follows ARC Framework — subtly, never as self-promotion

---

## 6. AI STACK

| Tool | Role |
|---|---|
| Cursor | Code execution (all prompts go through Cursor) |
| Claude | Strategy, QA, content, prompt writing (this role) |
| Midjourney Pro | Visual assets |
| ChatGPT | Brainstorming, operating brain |
| Perplexity | Research |
| Grok | X platform intelligence |

---

## 7. INFRASTRUCTURE

| Service | Purpose |
|---|---|
| Railway | Backend hosting (FastAPI) |
| GitHub | Repository (main branch, direct push) |
| Supabase | Auth + Database (user_profiles) |
| Stripe | Payments ($49/mo, 7-day trial) |
| Hetzner VPS | X Bot hosting |
| Kraken API | BTC/ETH price data |
| FRED API | Fed liquidity data (WALCL, TGA, RRP) |
| Alternative.me | Fear & Greed Index |
| CryptoCompare | Gap bridge data |

### 7.1 Supabase Schema

```sql
user_profiles:
  id, email, plan (free/paid),
  stripe_customer_id, stripe_subscription_id,
  subscription_status, current_period_end, created_at
```

### 7.2 Stripe Policy

`active/trialing/past_due → paid` | `canceled/incomplete/paused/unpaid → free`

---

## 8. DEVELOPMENT RULES

### 8.1 Cursor Prompt Protocol

Every Cursor prompt MUST begin with:
```
BEVOR du anfängst: Lies DEPLOY_STATE.md und permanent-fixes.mdc vollständig.
NACHDEM du fertig bist: Aktualisiere DEPLOY_STATE.md und permanent-fixes.mdc mit allen Änderungen.
```

### 8.2 Deploy Rules

- Prompts always deployed sequentially (never multiple simultaneously)
- Railway deployment verified between each prompt
- `DEPLOY_STATE.md` tracks all changes
- `.cursor/rules/permanent-fixes.mdc` tracks permanent architectural decisions

### 8.3 LOCKED CONSTANTS (NEVER CHANGE)

1. ARC Formula: `ma_200w × 0.35 + drawdown × 0.25 + liquidity × 0.25 + fear_greed × 0.15`
2. Zone Boundaries: 0–29 / 30–39 / 40–59 / 60–69 / 70–100
3. ARC stands for "AlphaCycle Risk Composite"
4. Zone names: Deep Value, Accumulation, Expansion, Risk Rising, Euphoria

### 8.4 Language Rules

- NO action-based language in user-facing text ("BUY", "SELL", "SIGNAL")
- Use regime-based language ("PHASE", "REGIME", "ENVIRONMENT")
- All interpretations historically-framed
- "Bottom Formation Signal" is the only exception (technical indicator name)

---

## 9. CURRENT STATUS

### 9.1 Deployed Features

- Premium UI Phase A–E (hero, spacing, color restraint, mobile, micro-polish)
- Trust Layer T-A/T-B/T-C (sources, badges, track record)
- ARC Chart (zoom, pan, auto-fit, clarity, markers)
- CSV Integration + Gap Fix
- Zone History Calendar-Day Fix
- Historical Returns Confirmed Periods
- Decision Engine 3-Layer Interpretation
- Signal Hierarchy Reorder
- Methodology Soft Gate
- Product Reframe (action → regime language)
- Consistency Patch (boundaries, phase labels)
- Hero Orbital Design (ring, dot, labels)
- X Bot (live on Hetzner)

### 9.2 Pending

- Stripe Live activation (awaiting legal structure — US LLC route)
- Alert Emails (Resend, after paid tier)
- Snapshot bug fix (`days_since_top` param)

---

## 10. REPOSITORY STRUCTURE

```
alphacycle/
├── index.html                    # Single-file frontend (~8800 lines)
├── backend/
│   ├── main.py                   # FastAPI app, all endpoints
│   ├── scoring.py                # ARC score computation
│   ├── decision_engine.py        # get_position(), allocation logic
│   ├── historical_returns.py     # compute_historical_returns()
│   ├── backtest_engine.py        # run_daily_backtest_full()
│   ├── snapshot.py               # build_snapshot() for X bot
│   ├── cycle_anchor.py           # Cycle phase, days since bottom/top
│   ├── fetcher.py                # API data fetching (Kraken, FRED, etc.)
│   ├── data/
│   │   └── btc_daily_kraken.csv  # Historical OHLC data
│   └── services/
├── docs/
│   └── alphacycle_context.md     # THIS FILE
├── DEPLOY_STATE.md               # Tracks all deployments
├── .cursor/
│   └── rules/
│       └── permanent-fixes.mdc   # Permanent architectural decisions
├── requirements.txt
└── Procfile                      # Railway deploy config
```

---

## 11. KEY API ENDPOINTS

| Endpoint | Returns |
|---|---|
| `/api/arc-summary` | Live ARC score, zone, components |
| `/api/historical-returns` | Forward returns by zone (confirmed periods) |
| `/api/zone-history` | Zone transition history (18 periods) |
| `/api/history-daily` | Daily ARC backtest data |
| `/api/history` | Weekly ARC data |
| `/api/cycle-anchor` | Days since bottom/top, cycle phase |
| `/api/prices` | Live BTC/ETH prices |
| `/api/backtest` | Full 10Y backtest results |
| `/api/snapshot` | Snapshot for X bot posts |
| `/api/liquidity-regime` | Fed liquidity regime data |
| `/api/short-term` | 30-90D near-term outlook |
| `/api/analyzer` | Multi-factor analysis |

---

## 12. CRITICAL AUDIT FINDINGS

From the March 2026 system audit:

1. **ARC is a REGIME classifier, not a timing signal.** It lags by design (200W MA component). Bottoms are identified ~10 days after the fact. Euphoria can persist with +60% upside.

2. **Track Record:** "All major cycle transitions since 2017 correctly classified" — no numeric claims (no "10/10" or "6/6").

3. **Euphoria Paradox:** Historical 12M forward returns from Euphoria entries are positive (+44%), but drawdowns average -41%. This is correctly handled by showing drawdown data for Euphoria instead of forward returns.

4. **FRED Liquidity Lag:** FRED data updates weekly (Thursday). Live ARC may be 3-7 days stale on the liquidity component. Source label includes "weekly" note.

---

*Last updated: 2026-04-11 (canonical path: docs/alphacycle_context.md)*
*Maintained by: Claude (Prompt Forge) + Noah*
