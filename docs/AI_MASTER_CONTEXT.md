# AlphaCycle — AI Master Context
# Complete System Architecture · ARC v1.2

> **Read `SYSTEM_TRUTH.md` first for immutable rules.**
> **This file is the canonical full-stack architecture document** (consolidates former `alphacycle_context.md`, operating manuals, and signal-architecture sections). Pair with `AI_AGENT_ROLES.md`, `AI_MASTER_PROMPT.md`, and `DEPLOY_STATE.md`.

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

See `SYSTEM_TRUTH.md` §1 for locked formula and weights (**ARC v1.2:** trend 0.35, drawdown 0.30, liquidity 0.15, sentiment 0.20).

### 2.1a Version and display transform

- **`backend/arc_config.py`:** `ARC_FORMULA_VERSION` tracks methodology (currently **v1.2** with the weights above). Bump only with explicit approval + documentation.
- **`arc_display_score(arc_raw, k=0.0)` in `backend/scoring.py`:** Default **k = 0** means **display equals raw** for API/UI (no stretch). Passing `k > 0` keeps the legacy stretch for special outputs only.
- **Hero in `index.html`:** Large ARC number and orbit use `arc_display` (same as raw when k=0); zone **name** under the gauge uses **raw** `arc_score` via `phaseOf(arcRaw)` (per `permanent-fixes.mdc`: Hero label + HR “YOU ARE HERE” raw rules).

### 2.2 Components

| Component | Weight | Source | Frequency | Scoring Function |
|---|---|---|---|---|
| Trend (200W MA Deviation) | 0.35 | Kraken BTC/USD OHLC | Daily | `ma_deviation_score()` |
| Drawdown (ATH Distance) | 0.30 | Kraken BTC/USD OHLC | Daily | `drawdown_score()` / `drawdown_score_hl()` |
| Liquidity (Fed Net Liquidity) | 0.15 | FRED (WALCL, TGA, RRP) | Weekly (Thu) | Impulse model §2.5 |
| Sentiment (Fear & Greed) | 0.20 | Alternative.me | Daily | `fg_to_score()` (inverted) |

### 2.3 Zone Boundaries

See `SYSTEM_TRUTH.md` §4. Canonical integer bands: **0–29 | 30–39 | 40–59 | 60–69 | 70–100**.

#### 2.3.1 Boundary implementation (operators)

**Canonical integer bands (same five zones as `SYSTEM_TRUTH` §4):** 0–29 | 30–39 | 40–59 | 60–69 | 70–100.

- **Zone name (API, Zone History, `zone_name` in `/api/arc-summary`):** `get_zone_name(arc_score)` in `backend/main.py` — `<= 29` Deep Value; `<= 39` Accumulation; `<= 59` Expansion; `<= 69` Risk Rising; else Euphoria.
- **Dashboard zone label:** `phaseOf(score)` in `index.html` — `< 30` Deep Value; `<= 39` Accumulation; `<= 59` Expansion; `<= 69` Risk Rising; else Euphoria. Matches integer ARC; at fractional scores 29–30 see source for edge behavior.
- **Zone colors:** `scoreColor(s)` in `index.html` uses `< 30`, `< 40`, `< 60`, `< 70` (five color bands aligned to the same zones).
- **Snapshot / some API labels:** `_phase_label(arc)` in `main.py` uses `< 30`, `< 40`, `< 60`, `< 70` (equivalent to the five zones).
- **Decision thresholds** in `decision_engine.get_position()` use separate numeric cuts; map to regime language via section 3.

Related: `zoneKey`, `renderDecisionInterpretation()`, Historical Returns grids — always use the same five zone names and boundaries as above.

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

### 4.3 Blur-Gate System (`applyBlurGates()` in `index.html`)

**Rules:** `effectivePlan` treats `trial` like `paid`. **Free-tier gates** (`gateInfo.tier === 'free'`): locked only when `effectivePlan === 'anonymous'` (signup unlocks). **Paid-tier gates:** locked whenever `effectivePlan !== 'paid'`.

| Gate ID | Tier in code | Lock behavior |
|---|---|---|
| gate-hero | free | Anonymous only |
| gate-historical-returns | free | Anonymous only |
| gate-cycle-overview | paid | Non–paid users |
| gate-near-term | paid | Non–paid users |
| gate-arc-history | paid | Non–paid users |
| gate-arc-momentum | paid | Non–paid users |
| gate-decision-engine | paid | Non–paid users |
| gate-zone-history | paid | Non–paid users |
| gate-content-export | paid | Non–paid users |
| gate-live-prices | (not in `gateInfo`) | **Never locked** — code removes `locked` every run |

Compact reference (content summary):

| Gate | Tier | Content |
|---|---|---|
| gate-hero | free | Score, zone, context |
| gate-historical-returns | free | Full HR data |
| gate-decision-engine | paid | Positioning Framework |
| gate-cycle-overview | paid | Cycle phase (see `gateInfo` above) |
| gate-near-term | paid | 30-90D outlook |
| gate-arc-history | paid | 10Y chart |
| gate-zone-history | paid | Zone history |

### 4.4 Historical Returns

- Uses **confirmed zone periods** from `compute_zone_history()` (~18 entries), not raw daily crossings (was 257 before fix).
- Forward returns calculated with **calendar-day** lookup (91/182/365 days).
- Current zone displayed as single dominant block; others as dim reference line.
- Original 5-zone grid hidden (`hr-grid { display: none !important; }` where applied) — `hr-*` IDs remain in DOM for `fetchHistoricalReturns` / `applyHistoricalReturnsCurrentZone`.

### 4.5 ARC Chart

- Chart.js + `chartjs-plugin-zoom@2.0.1` + Hammer.js (X-axis zoom/pan; min visible range ~30 days).
- `autoFitPriceAxis()` with re-entrancy guard (BTC price axis fits visible window).
- 10Y default zoom to last **2 years** (~730 points); reset → 2Y view; double-click → full 10Y.
- Zone band overlays (`zoneRects`), cycle markers, crosshair, current price label on right edge.

### 4.6 Signal Summary

Hidden via CSS + JS (`display: none`). Redundant with Hero + Positioning Framework.

---

## 5. DISTRIBUTION SYSTEM

### 5.1 X Bot

| Field | Value |
|---|---|
| Server | Hetzner VPS (`ubuntu-4gb-hel1-2`, `95.216.152.31`) |
| Stack | Python 3 + Tweepy v2 + Anthropic Claude API |
| Scan | **42** tracked accounts (11+16+15 tiers); default **3600s** scan interval (see `config.py` / `.env`) |
| Scanner filters | (1) **BLOCKED_KEYWORDS** — all tiers (sports/spam etc.). (2) **RELEVANT_KEYWORDS** — **Tier 2+3** only; **Tier 1** (`TIER_1_ACCOUNTS`, match author handle case-insensitive) **skips** step 2 (curated = always on-topic for keyword gate). Expanded macro/economy/CB/energy/fixed-income/news keyword list in `config.py`. |
| VPS deploy | X-bot code on Hetzner: **push to `main` → GitHub webhook → `deploy-server`** (see `alphacycle-x-bot/deploy-server/README.md`). No requirement for a local Windows Python import check to validate deploy. |
| Limits | Defaults include **REPLY_LIMIT_HOURLY=5**, **REPLY_LIMIT_DAILY=15**, **MIN_LIKES_TO_REPLY=0**, delay **30-120s**, author spacing + per-account daily caps (see `permanent-fixes.mdc` X-Bot section) |
| Reply rules | Target **max 260** chars in prompts/QA; Telegram handoff for posts/replies (no blind auto-post to X for replies) |
| Primary Claude | **`claude-opus-4-6`** in `config.CLAUDE_MODEL` for **replies and daily posts** (higher API cost than Sonnet; monitor usage). QA remains **Haiku** (`QA_MODEL`). |
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

## 7. MASTERPROMPT SYSTEM

### What is a Masterprompt?

A masterprompt is a detailed, QA-reviewed instruction set that Cursor executes exactly. It contains:

1. **PFLICHT block** — read `DEPLOY_STATE.md` + `permanent-fixes.mdc` before starting
2. **Locked constraints** — what must NOT change
3. **Goal** — what the prompt achieves
4. **Implementation** — exact steps with code snippets
5. **Validation checklist** — how to verify success
6. **Deliverable** — `git add` / `git commit` / `git push` with message

### Prompt Lifecycle

```
[Need identified] → [ChatGPT writes spec] → [Claude writes prompt]
→ [Noah QA reviews] → [Corrections applied] → [Cursor executes]
→ [Noah verifies live] → [Done or revert]
```

### QA Review Protocol

Before any prompt is approved, check:

1. Does it reference actual class/ID names? (not guessed)
2. Does it break any locked constants?
3. Does it conflict with previously deployed changes?
4. Are there CSS specificity conflicts?
5. Does it handle mobile?
6. Does it preserve all element IDs for JS compatibility?

---

## 8. PHASE 1 OBJECTIVES (CURRENT)

### 8.1 Immediate (Pre-Revenue)

| Priority | Task | Status |
|---|---|---|
| 1 | Hero Orbit Mobile Fix (labels, ring size, overlaps) | In progress |
| 2 | Snapshot (`days_since_top`) | Done |
| 3 | X Bot optimization (reply quality, QA loop, Telegram handoff) | In progress |
| 4 | Auth "failed to fetch" bug | Needs investigation |

### 8.2 Revenue Activation

| Priority | Task | Blocker |
|---|---|---|
| 1 | Legal structure (US LLC Wyoming) | Noah action |
| 2 | Stripe Live activation | Legal structure |
| 3 | Paid tier launch ($49/mo) | Stripe Live |
| 4 | Alert Emails (Resend) | After paid tier |

### 8.3 Growth Targets

```
X Followers: 100 → 200 → 500 → 1,000 → 2,000 → 5,000 → 10,000
SaaS launch: After ~500 followers
Paid tier: $49/mo with 7-day trial
```

---

## 9. KNOWN ISSUES AND TECH DEBT

1. **CoinCap API failing:** `FAILED https://api.coincap.io/v2/assets: [Errno -2]` — not critical; other sources cover gaps.
2. **`days_since_top` snapshot path:** Resolved in code — `build_snapshot()` accepts `days_since_top`; `main.py` passes `st_ctx.get("days_since_top")` (verify in `DEPLOY_STATE` if regressions appear).
3. **Auth "failed to fetch":** Supabase connection issue — needs DevTools investigation.
4. **CSS specificity wars:** Multiple `!important` overrides from iterative prompts — needs consolidation pass.
5. **Track highlight vs. landing:** `#track-dv-return` must match `/api/historical-returns` `zones.deep_value.avg_12m` (e.g. +236.4% after ARC v1.2); landing/teaser cards use **specific event** forward returns and are not the same as zone averages.
6. **Zone History data mismatch:** Confirmed zone vs live ARC can disagree — UI section may be hidden pending fix; treat as product risk until resolved.
7. **Orbit label positioning:** Labels may overlap ring on some viewports.

---

## 10. EMERGENCY PROCEDURES

### Site broken after deploy

```bash
git log --oneline -10          # Find last good commit
git checkout <hash> -- index.html
git add index.html
git commit -m "revert: restore stable index.html"
git push
```

### Bot posting garbage

```bash
ssh root@95.216.152.31
screen -r alphacycle
# Ctrl+C to stop
# Fix reply_engine.py / prompts
python3 bot.py
```

### Railway deploy stuck

Check Railway dashboard → Deployments → latest build logs. If build fails, check `requirements.txt` for version conflicts.

---

## 11. API REFERENCE

| Endpoint | Returns |
|---|---|
| `/health` | Service health JSON |
| `/api/prices` | Live BTC/ETH prices |
| `/api/cycle/btc` | BTC cycle payload |
| `/api/cycle/eth` | ETH cycle payload |
| `/api/cycle/macro` | Macro cycle payload |
| `/api/cycle/combined` | Combined cycle view |
| `/api/arc-summary` | Live ARC score, zone, components, decision |
| `/api/historical-returns` | Forward returns by zone (confirmed periods) |
| `/api/zone-history` | Zone transition history (~18 periods) |
| `/api/history-daily` | Daily ARC scores (last 365 days) |
| `/api/history` | History payload (legacy/compatibility) |
| `/api/fear-greed` | Fear and Greed index |
| `/api/backtest` | Full 10Y backtest results |
| `/api/cycle-anchor` | Days since bottom/top, cycle phase |
| `/api/snapshot` | Snapshot for X bot posts |
| `/api/liquidity-regime` | Fed liquidity regime data |
| `/api/short-term` | 30-90D near-term outlook |
| `/api/analyzer` | Multi-factor analysis |
| `/api/decision` | Decision engine output |
| `/api/subscribe` | Email capture (Supabase `email_captures`) |
| `/api/auth/profile` | Auth plan / subscription snapshot |

---

## 12. REPOSITORY STRUCTURE

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
│   ├── AI_MASTER_CONTEXT.md            # THIS FILE (full architecture)
│   ├── SYSTEM_TRUTH.md                 # Immutable rules (ARC v1.2)
│   ├── AI_AGENT_ROLES.md               # Agent definitions + init protocol
│   └── AI_MASTER_PROMPT.md             # Behavioral rules + Cursor appendix
├── DEPLOY_STATE.md                     # Deployment tracking
├── .cursor/rules/permanent-fixes.mdc   # Permanent architectural decisions
└── Procfile                            # Railway config
```

---

## 13. CRITICAL AUDIT FINDINGS

1. **ARC is a regime classifier, not a timing signal.** Lags by design (200W MA). Bottoms identified ~10 days after. Euphoria can persist with +60% upside.

2. **Track Record:** "All major cycle transitions since 2017 correctly classified" — no numeric claims.

3. **Euphoria Paradox:** 12M forward returns from Euphoria entries are positive (+44%), but drawdowns average −41%. UI shows drawdown, not forward return.

4. **FRED Liquidity Lag:** 3–7 days stale. Source label includes "weekly" note.

5. **Hi/Lo Parity:** Live ARC must use daily OHLC (high/low) to match backtest methodology. Without Hi/Lo, live score diverges from chart.

---

## 14. SIGNAL ARCHITECTURE (SEVEN LAYERS)

AlphaCycle operates as a layered intelligence system. Each layer transforms raw inputs into increasingly refined outputs. No layer operates in isolation. The system is designed so that each layer feeds the next in a strict sequence.

### Layer 1 — Data Layer

Raw market data ingested from external sources. This is the foundation. No interpretation happens here — only collection and validation.

Sources:

- **BTC Price Data** — Kraken API (spot prices, OHLC, weekly candles)
- **Fed Liquidity Data** — FRED API (WALCL, TGA, RRP → Net Liquidity = WALCL - TGA - RRP)
- **Fear & Greed Sentiment** — Alternative.me API (0-100 index)
- **Market Structure Inputs** — DeFiLlama (TVL, stablecoin supply), OKX (funding rates)

Data is validated before entering the signal layer. Stale data (>6h) is flagged. Missing sources reduce confidence scoring.

#### Data Integrity Fail-Safes

If any primary data source becomes unavailable:

1. The system must continue operating using the last verified datapoint.
2. Confidence scoring must automatically decrease.
3. The dashboard must display a degraded-data warning.

ARC calculations must never halt entirely due to temporary data outages.

### Layer 2 — Signal Layer

Raw data is normalized into comparable 0-100 scores. Each signal isolates one structural dimension of the market.

Four signals:

- **Trend Signal** — Measures BTC price relative to the 200-week moving average. Low score = price far below mean (historically favorable). High score = price far above mean (historically extended).
- **Drawdown Signal** — Measures current decline from all-time high ($126,000). Low score = deep drawdown (historically favorable). High score = near ATH (historically risky).
- **Liquidity Signal** — Measures global liquidity conditions via Fed Net Liquidity + stablecoin supply + DeFi TVL. Low score = liquidity contracting. High score = liquidity expanding.
- **Sentiment Signal** — Measures crowd emotion via Fear & Greed Index. Low score = extreme fear. High score = extreme greed. This is ONE input into the composite, not the composite itself.

Each signal is independently useful but incomplete alone. The composite layer combines them.

#### Signal Normalization

Each signal is transformed into a 0–100 score using deterministic normalization functions.

Normalization methods may include:

- percentile ranking
- z-score transformation
- bounded scaling functions
- historical distribution mapping

The exact normalization formula for each signal is defined in the implementation layer and documented in the repository.

Normalization rules must remain stable across time to ensure comparability of historical ARC scores.

Changes to normalization logic require:

1. Explicit approval by Noah
2. Version update of the ARC methodology
3. Documentation in methodology change logs

### Layer 3 — Composite Layer

**ARC — AlphaCycle Risk Composite**

The four signals are weighted and combined into a single structural risk score.

```
ARC = ma_200w × 0.35 + drawdown × 0.30 + liquidity × 0.15 + fear_greed × 0.20
```

Output: A score from 0 to 100.

#### Deterministic Calculation Rule

The ARC score is a deterministic calculation derived solely from the four signal inputs.

No manual adjustments, discretionary overrides, or AI interpretations are permitted in the ARC calculation process.

ARC must always be reproducible from raw data inputs.

#### Recalculation Protocol

ARC is recalculated on a fixed schedule using the most recent validated data inputs.

Default calculation interval:

- Daily recalculation at 00:00 UTC.

If any underlying data source updates within the calculation window, the ARC score is recomputed during the next scheduled run.

Manual recalculation is not permitted unless explicitly initiated by Noah for debugging or data correction purposes.

Every recalculation must generate:

- Timestamp
- Source data snapshot
- Component scores
- Final ARC score
- Zone classification

These records are stored for full historical auditability.

Zone classification:

- **0-29: Deep Value** — Historically strongest forward returns. Maximum structural opportunity.
- **30-39: Accumulation** — Structure resetting. Early positioning phase.
- **40-59: Expansion** — Mid-cycle. Structure supports continuation.
- **60-69: Risk Rising** — Structural risk elevating. Caution warranted.
- **70-100: Euphoria** — Historically weakest forward returns. Maximum structural risk.

**Governance:** Zone boundaries match `SYSTEM_TRUTH.md` §4. **Weights** are versioned in `backend/arc_config.py` (`ARC_FORMULA_VERSION`, **v1.2** as of consolidation). Any change requires the methodology process in `SYSTEM_TRUTH.md` §11 (research, backtest, documentation, version bump, reproducibility).

### Layer 4 — Context Layer

Context engines interpret the ARC score within larger market structures. ARC alone tells you the risk level. Context tells you what that risk level means given the broader environment.

Context engines include:

- **Cycle Overview** — Days since cycle top, estimated days to cycle bottom, cycle phase classification (Early Bear, Mid Bear, Late Bear, Early Bull, Mid Bull, Late Bull).
- **Seasonality** — Historical return patterns by month and by position within the halving cycle.
- **Macro Context** — Geopolitical backdrop, Fed policy regime, equity market correlation/decoupling, oil/energy market stress.
- **Momentum** — 30-day ARC momentum (direction of change), percentile ranking against all history.

Context layers add narrative depth. They do not modify the ARC score.

### Layer 5 — Decision Layer

The Decision Engine translates the ARC zone and context into actionable allocation frameworks.

Outputs:

- **Suggested Position** — Deep Value / Accumulation / Hold / Risk Reduction / Exit
- **Spot Allocation Range** — Percentage range (e.g. 35-50%)
- **12-Month Expected Return** — Historical average return from current zone
- **Win Rate** — Historical probability of positive 12-month return from current zone
- **Confidence** — Low / Low-Moderate / Moderate / High (based on data completeness and signal alignment)

The Decision Engine provides frameworks, not financial advice. It measures structural positioning. It does not predict price.

### Layer 6 — Product Layer

**AlphaCycle Dashboard (alphacycle.app)**

The dashboard is the interface for accessing the framework. It surfaces:

- ARC score with radial gauge visualization
- Four component scores with individual gauges
- Decision Engine outputs
- ARC History chart with zone overlays
- Cycle Overview with timeline estimates
- Backtest returns by zone
- Data source status indicators
- Clean Data Export for content generation

The dashboard is NOT the product. The framework is the product. The dashboard is the window into the framework.

### Layer 7 — Distribution Layer

Intelligence outputs distributed through multiple channels:

- **Dashboard** — Real-time ARC readings and analysis (alphacycle.app)
- **X Bot** — Automated daily posts and replies via the AlphaCycle Growth Engine
- **Research Reports** — Weekly ARC summaries, cycle analysis (future: newsletter, paid research)
- **Alerts** — Zone change notifications, structural shift alerts (future: email via Resend, Telegram)
- **API** — Institutional data access (future: paid API tier)

Each distribution channel reinforces the same positioning: AlphaCycle is Bitcoin Cycle Intelligence. Structure before emotion.

### Historical Data Integrity

Backtest datasets used in AlphaCycle must remain immutable.

Historical datasets may be expanded with new data, but previously recorded historical values must never be modified.

This ensures consistency of published historical performance statistics.

### Data Versioning

All historical datasets used by AlphaCycle must be versioned.

Each dataset update must create a new version snapshot containing:

- dataset timestamp
- source provider
- transformation logic version
- checksum hash

Older dataset versions must remain accessible to allow reconstruction of past ARC calculations.

This guarantees full reproducibility of historical ARC scores.

---

## 15. LONG-TERM VISION

AlphaCycle is not a dashboard. It is not a content account. It is not a trading signal service.

AlphaCycle is evolving toward a **market intelligence platform** that creates structural information advantage for investors navigating crypto cycles.

### Current State (2026)

```
LIVE:
├── ARC Composite scoring (4 components, 5 zones)
├── Decision Engine (allocation frameworks)
├── Dashboard (alphacycle.app)
├── X Bot (automated posts + replies)
├── Telegram approval system
├── Clean Data Export
└── 8 years of backtested data
```

### Near-Term Evolution (6-12 months)

```
PLANNED:
├── Paid SaaS tier (Stripe, $19-49/month)
├── Alert system (zone changes, structural shifts via email/Telegram)
├── Email capture: POST `/api/subscribe` → Supabase `email_captures` (no Beehiiv server-side sync)
├── Blur-gate system (free tier sees ARC score, paid tier sees components + backtest)
├── Enhanced backtest with 5-zone granularity
└── Track record documentation (predicted vs actual outcomes)
```

### Long-Term Capabilities (12-36 months)

AlphaCycle will expand from a single-composite system to a multi-layered intelligence platform:

**Regime Classification**
Beyond the current 5-zone system, AlphaCycle will classify market regimes with higher granularity — combining ARC zones with macro regime data, cycle phase positioning, and cross-asset correlation shifts. The goal is automated regime labeling that institutions can subscribe to.

**Cycle Modeling**
Building on the current Cycle Overview engine, AlphaCycle will develop probabilistic cycle models that estimate phase durations, transition probabilities, and historical analogs. Not predictions — probability distributions based on structural data.

**Macro Liquidity Analysis**
Expanding the current Net Liquidity tracking (WALCL - TGA - RRP) into a comprehensive liquidity intelligence layer. This includes global central bank balance sheet monitoring, credit market stress indicators, and real-time liquidity flow direction analysis.

**Capital Flow Intelligence**
Tracking where capital moves across the crypto ecosystem. Stablecoin minting/burning, exchange inflows/outflows, whale wallet movements, DeFi TVL migration between chains. The goal is answering: "Where is the money going?" in real time.

**Narrative Detection**
AI-powered analysis of Crypto Twitter, news sources, and community sentiment to identify emerging narratives before they become consensus. Which themes are gaining traction? Which are fading? How do narrative shifts correlate with structural positioning?

**Institutional Research Products**
Premium research reports combining all intelligence layers into actionable frameworks for institutional investors. Weekly cycle reports, monthly macro overlays, quarterly strategy reviews. Distributed via newsletter, dashboard, and eventually a dedicated research portal.

#### Data Network Effects

The long-term advantage of AlphaCycle comes from cumulative data depth.

Every additional market cycle increases:

- backtest robustness
- regime classification accuracy
- institutional trust

This creates a compounding information advantage that new competitors cannot easily replicate.

### Design Principles

Every capability AlphaCycle builds must adhere to these principles:

```
1. MEASURE, DON'T PREDICT
   AlphaCycle measures structural risk. It does not predict price.
   Every output is a measurement or a probability, never a certainty.

2. STRUCTURE BEFORE EMOTION
   The platform exists because sentiment-driven decisions
   consistently underperform structure-driven decisions.
   Every feature must reinforce this thesis.

3. INFORMATION ADVANTAGE, NOT TRADING SIGNALS
   AlphaCycle creates asymmetric information advantage.
   It helps investors understand WHERE they are in the cycle.
   What they DO with that information is their decision.

4. TRUST IS THE PRODUCT
   In a market full of noise, trust is the scarcest resource.
   Every feature, every post, every data point must strengthen trust.
   One false claim destroys more trust than a hundred correct ones build.

5. COMPOUND OVER TIME
   The value of cycle intelligence compounds.
   Track record, historical data, backtest depth, audience trust —
   all of these grow stronger with time. AlphaCycle is designed
   for long-term compounding, not short-term virality.
```

### Strategic Positioning

AlphaCycle operates at the intersection of three domains:

1. Macro Research
2. Quantitative Market Analysis
3. Crypto Cycle Intelligence

The platform bridges institutional-style macro frameworks with the unique structural dynamics of the crypto market.

### The Endgame

AlphaCycle becomes the definitive source for Bitcoin cycle intelligence — the platform that serious investors check before making structural decisions. Not because it predicts the future, but because it measures the present more accurately than anything else available.

The ARC Index becomes a recognized, cited, debated framework — like Stock-to-Flow, the Rainbow Chart, or the Pi Cycle Top Indicator. But unlike those single-metric models, ARC is a composite. Four dimensions. One score. Continuously refined by data, not by narrative.

**Structure before emotion. Always.**

### Methodology Governance

AlphaCycle operates under strict methodology governance.

ARC methodology changes are extremely rare and must follow a formal process:

1. Research justification
2. Historical backtest evaluation
3. Public documentation of rationale
4. Versioned methodology update

Any change must preserve the ability to reproduce historical ARC scores under the previous version.

If a change occurs, the system will label:

- ARC v1
- ARC v2
  etc.

The current production system always runs the latest approved version.

---

*Consolidates (archived paths removed): `alphacycle_context.md`, `alphacycle_ai_operating_manual.md`, `alphacycle_ai_operating_manual_COMPLETE.md`, `AlphaCycle-AI-Manual-Sections-11-13-FINAL-v2.md` — content merged here and in `AI_AGENT_ROLES.md` / `AI_MASTER_PROMPT.md` as applicable.*

*ARC Version: v1.2 · Last updated: 2026-04-12*
