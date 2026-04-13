# AlphaCycle — AI Master Context
# Complete System Architecture · ARC v1.1

> **Read `SYSTEM_TRUTH.md` first for immutable rules.**
> **This file is the stack-level architecture summary.** Extended detail remains in `docs/alphacycle_context.md` and `docs/alphacycle_ai_operating_manual_COMPLETE.md` (do not delete them).

---

## 1. PROJECT OVERVIEW

AlphaCycle is a live Bitcoin Cycle Intelligence SaaS that classifies the current market regime using the ARC Index (0–100). It is a **regime classification system**, NOT a trading signal tool.

| Field | Value |
|---|---|
| Product | https://alphacycle.app |
| Backend | FastAPI on Railway (`alphacycle-production.up.railway.app`) |
| Frontend | Single-file `index.html` (~8700+ lines) |
| Auth/DB | Supabase |
| Payments | Stripe ($49/mo, 7-day trial) — test mode |
| X Bot | Python on Hetzner VPS |
| Telegram | Approval system for bot posts |
| Owner | Noah (sole operator, BRT timezone) |

---

## 2. ARC ENGINE

### 2.1 Formula

See `SYSTEM_TRUTH.md` §1 for locked formula and weights.

### 2.2 Components

| Component | Weight | Source | Frequency | Scoring Function |
|---|---|---|---|---|
| Trend (200W MA Deviation) | 0.35 | Kraken BTC/USD OHLC | Daily | `ma_deviation_score()` |
| Drawdown (ATH Distance) | 0.25 | Kraken BTC/USD OHLC | Daily | `drawdown_score()` / `drawdown_score_hl()` |
| Liquidity (Fed Net Liquidity) | 0.25 | FRED (WALCL, TGA, RRP) | Weekly (Thu) | Impulse model §2.4 |
| Sentiment (Fear & Greed) | 0.15 | Alternative.me | Daily | `fg_to_score()` (inverted) |

### 2.3 Zone Boundaries

See `SYSTEM_TRUTH.md` §4. Canonical: `< 30 / < 40 / < 60 / < 70`.

### 2.4 Liquidity Impulse Model

```
Impulse Score = 50.0 − (30d_change × 2.5) − (90d_change × 1.5)
```

Net Liquidity = WALCL − TGA − RRP. Requires ≥22 data points. Fallback: `macro_liq` from `compute_btc_score()`.

### 2.5 Extreme Condition Boost (ECB)

See `SYSTEM_TRUTH.md` §2. Dual-extreme signals add ±3 or ±7.

### 2.6 Display Transform

See `SYSTEM_TRUTH.md` §3. **Default `k=0`:** display equals raw. Optional `k>0` only for explicit stretch; UI/API default matches production.

### 2.7 Hi/Lo Engine

When daily OHLC available: `ma_score` uses daily high vs 200W MA, `dd_score` uses daily low vs ATH range. Ensures live score matches backtest methodology.

**Source:** `fetch_kraken_ohlc_latest()` in `fetcher.py` → cached as `CACHE["ohlc_latest"]` → passed to `compute_arc_score(weekly_high=, weekly_low=)`.

### 2.8 Data Pipeline

```
CSV (2013-10-06 → 2024-03-30, 3817 rows)
    ↓
CryptoCompare Gap Bridge (2024-01 → 2024-03)
    ↓
Kraken API (2024-03-31 → present, daily OHLC)
    ↓
run_daily_backtest_full() → 3135+ daily ARC data points (2017-08-17 → present)
```

---

## 3. DECISION ENGINE

### 3.1 Backend Positions

See `SYSTEM_TRUTH.md` §7.

### 3.2 Frontend Display Mapping

Backend values mapped to regime language via `positionDisplay` object. See `SYSTEM_TRUTH.md` §7.

### 3.3 3-Layer Interpretation (Positioning Framework)

1. **Zone name + ARC score** eyebrow
2. **Interpretation** — 1–2 sentences, historically-framed
3. **Typical Positioning** — 3–4 bullet points
4. **Disclaimer** — "THIS REFLECTS HOW SIMILAR ENVIRONMENTS BEHAVED HISTORICALLY"

Risk/Reward Profile (Layer 3) is hidden via CSS (`dec-layer-3 { display: none }`).

---

## 4. DASHBOARD

### 4.1 Section Order

```
gate-hero                  Hero with Orbital Ring
hero-cta-block             CTA (anonymous only)
HISTORICAL CONTEXT         separator
gate-historical-returns    Single dominant zone block + secondary line
gate-live-prices           BTC, ETH, Fear & Greed (compact)
gate-decision-engine       Positioning Framework (2x2 grid + interpretation)
gate-cycle-overview        Cycle Phase, Days Since Bottom/Top
gate-near-term             30-90D Outlook
DEEP ANALYSIS              separator
gate-arc-history           10Y ARC Chart (zoom/pan/auto-fit)
gate-arc-momentum          ARC Momentum (30D bar chart)
gate-zone-history           HIDDEN (data mismatch — pending fix)
```

### 4.2 Hero — Orbital Design

- Conic gradient ring via `::before` pseudo-element with CSS mask
- Score centered inside ring: `clamp(68px, 10vw, 88px)`
- Dot on ring: `(score/100) × 360° − 90°`, zone-colored glow
- 5 zone labels outside ring: `.ol-dv`, `.ol-ac`, `.ol-ex`, `.ol-rr`, `.ol-eu`
- Functions: `positionOrbitDot(score)`, `highlightOrbitZone(score)`
- Old gauge SVG hidden via CSS (`display: none`)

### 4.3 Blur-Gate System

| Gate | Tier | Content |
|---|---|---|
| gate-hero | free | Score, zone, context |
| gate-historical-returns | free | Full HR data |
| gate-decision-engine | paid | Positioning Framework |
| gate-cycle-overview | free | Cycle phase |
| gate-near-term | paid | 30-90D outlook |
| gate-arc-history | paid | 10Y chart |
| gate-zone-history | paid | Zone history (currently hidden) |

### 4.4 ARC Chart

- Chart.js + `chartjs-plugin-zoom@2.0.1` + Hammer.js
- `autoFitPriceAxis()` with re-entrancy guard
- 10Y default zoom to last 2Y (730 points)
- Reset → 2Y, Double-click → full 10Y
- Zone band overlays, cycle markers, crosshair
- Current price label on right edge

### 4.5 Historical Returns

- Confirmed zone periods from `compute_zone_history()` (~18 entries)
- Forward returns: calendar-day lookup (91/182/365 days)
- Display: single dominant zone block (focus) + dim secondary reference line
- Original 5-zone grid hidden (`hr-grid { display: none }`)

### 4.6 Signal Summary

Hidden via CSS + JS (`display: none`). Redundant with Hero + Positioning Framework.

---

## 5. DISTRIBUTION SYSTEM

### 5.1 X Bot

| Field | Value |
|---|---|
| Server | Hetzner VPS (`ubuntu-4gb-hel1-2`, `95.216.152.31`) |
| Stack | Python 3 + Tweepy v2 + Anthropic Claude API |
| Scan | 20 tracked accounts, 300s interval |
| Limits | 6/hr, 20/day, 360–1320s random delay |
| Reply rules | Max 180 chars, curiosity gap, no self-promo, no financial advice |
| ARC Context | Fetches live from `/api/arc-summary` |

**Bot files:**
```
alphacycle-x-bot/
├── bot.py                  Main loop
├── config.py               Keys (env vars), tracked accounts, limits
├── scanner.py              Twitter API v2 tweet fetching
├── reply_engine.py         Claude API reply generation
├── poster.py               Twitter posting with rate limits
├── daily_post_engine.py    Scheduled daily posts (6 types)
├── growth_engine.py        Follower growth strategy
├── database.py             SQLite tracking
├── telegram_bot.py         Telegram integration
├── telegram_listener.py    Telegram approval system
└── generate_banner.py      Visual banner generation
```

### 5.2 Telegram Approval System

Bot posts are routed through Telegram for Noah's approval before publishing to X. Prevents low-quality or off-brand content from going live.

### 5.3 Content Strategy

- 6 post types: Contrarian Signal, Structural Insight, Contrast, Cycle Pattern, Narrative, Weekly Update
- Posting windows: 10:00 BRT + 20:00 BRT (US Prime Time)
- Reply strategy against Tier-1 crypto analyst list

---

## 6. INFRASTRUCTURE

| Service | Purpose | Status |
|---|---|---|
| Railway | Backend hosting | ✅ Live |
| GitHub | Repository (main branch) | ✅ Active |
| Supabase | Auth + DB | ✅ Free tier (cronjob keep-alive) |
| Stripe | Payments | ⏳ Test mode |
| Hetzner VPS | X Bot + Telegram | ✅ Live |
| Kraken API | BTC/ETH OHLC | ✅ Primary |
| FRED API | WALCL, TGA, RRP | ✅ Weekly |
| Alternative.me | Fear & Greed | ✅ Daily |
| CryptoCompare | Gap bridge | ✅ One-time |
| OKX | Funding rates | ✅ Live |

### Supabase Schema

```sql
user_profiles: id, email, plan (free/paid),
  stripe_customer_id, stripe_subscription_id,
  subscription_status, current_period_end, created_at

alert_log: id, triggered_at, arc_score, zone_from, zone_to
email_captures: (email collection)
```

---

## 7. API ENDPOINTS

| Endpoint | Returns |
|---|---|
| `/api/arc-summary` | Live ARC score, zone, components, decision |
| `/api/historical-returns` | Forward returns by zone (confirmed periods) |
| `/api/zone-history` | Zone transition history (~18 periods) |
| `/api/history-daily` | Daily ARC scores (last 365 days) |
| `/api/backtest` | Full 10Y backtest results |
| `/api/cycle-anchor` | Days since bottom/top, cycle phase |
| `/api/prices` | Live BTC/ETH prices |
| `/api/snapshot` | Snapshot for X bot posts |
| `/api/liquidity-regime` | Fed liquidity regime data |
| `/api/short-term` | 30-90D near-term outlook |
| `/api/analyzer` | Multi-factor analysis |
| `/api/decision` | Decision engine output |

---

## 8. REPOSITORY STRUCTURE

```
alphacycle/
├── index.html                          # Single-file frontend
├── backend/
│   ├── arc_config.py                   # CANONICAL: ARC formula, weights, zones
│   ├── main.py                         # FastAPI app + all endpoints
│   ├── scoring.py                      # ARC score computation
│   ├── decision_engine.py              # get_position(), allocations
│   ├── historical_returns.py           # Forward return calculations
│   ├── fetcher.py                      # External API data fetching
│   ├── cycle_anchor.py                 # Cycle phase logic
│   ├── snapshot.py                     # X bot snapshot builder
│   ├── liquidity_engine.py             # Liquidity regime
│   ├── analyzer.py                     # Multi-factor analyzer
│   ├── seasonality.py                  # Seasonal patterns
│   ├── auth.py                         # Supabase auth
│   ├── database.py                     # DB helpers
│   ├── data/btc_daily_kraken.csv       # Historical OHLC
│   └── services/backtest_engine.py     # Daily backtest
├── alphacycle-x-bot/                   # X Bot + Telegram
├── docs/
│   ├── AI_MASTER_CONTEXT.md            # THIS FILE
│   ├── SYSTEM_TRUTH.md                 # Immutable rules
│   ├── AI_AGENT_ROLES.md               # Agent definitions
│   ├── AI_MASTER_PROMPT.md             # Universal loading prompt
│   └── alphacycle_context.md           # Legacy (superseded by this file)
├── DEPLOY_STATE.md                     # Deployment tracking
├── docs/CURSOR_MASTERPROMPT.md         # Cursor-specific instructions
├── .cursor/rules/permanent-fixes.mdc   # Permanent architectural decisions
└── Procfile                            # Railway config
```

---

## 9. CRITICAL AUDIT FINDINGS

1. **ARC is a regime classifier, not a timing signal.** Lags by design (200W MA). Bottoms identified ~10 days after. Euphoria can persist with +60% upside.

2. **Track Record:** "All major cycle transitions since 2017 correctly classified" — no numeric claims.

3. **Euphoria Paradox:** 12M forward returns from Euphoria entries are positive (+44%), but drawdowns average −41%. UI shows drawdown, not forward return.

4. **FRED Liquidity Lag:** 3–7 days stale. Source label includes "weekly" note.

5. **Hi/Lo Parity:** Live ARC must use daily OHLC (high/low) to match backtest methodology. Without Hi/Lo, live score diverges from chart.

---

## 10. KNOWN ISSUES

1. **Zone History data mismatch** — confirmed zone is Expansion but live ARC is Accumulation. Section hidden until fixed.
2. **Snapshot `days_since_top`** — `build_snapshot()` missing parameter.
3. **CSS specificity accumulation** — multiple `!important` overrides from iterative prompts.
4. **Orbit label positioning** — labels may overlap ring on some viewports.
5. **CoinCap API failing** — `ERR_NAME_NOT_RESOLVED`. Non-critical, data from other sources.

---

*Supersedes: `docs/alphacycle_context.md`*
*ARC Version: v1.1 · Last updated: 2026-04-10*
