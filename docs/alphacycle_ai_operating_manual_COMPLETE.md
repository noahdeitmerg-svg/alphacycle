# AlphaCycle — AI Operating Manual

> **Every AI agent MUST read this file + `docs/alphacycle_context.md` before executing any task.**

---

## 1. PROJECT OVERVIEW

AlphaCycle is a live Bitcoin Cycle Intelligence SaaS. It classifies the current market regime using the ARC Index (0–100) — a composite of trend, drawdown, liquidity, and sentiment.

- **Product:** https://alphacycle.app
- **Backend:** FastAPI on Railway
- **Frontend:** Single-file `index.html` (~8800 lines)
- **Auth/DB:** Supabase
- **Payments:** Stripe ($49/mo, 7-day trial)
- **X Bot:** Python on Hetzner VPS
- **Owner:** Noah (sole operator)

**AlphaCycle is NOT a trading signal tool. It is a regime classification system.**

---

## 2. REPOSITORY AUDIT SUMMARY

### What exists and is deployed:

| System | Status | Location |
|---|---|---|
| ARC Engine (scoring, backtest, zone logic) | ✅ Live | `backend/scoring.py`, `backtest_engine.py` |
| Decision Engine (positioning framework) | ✅ Live | `backend/decision_engine.py` |
| Historical Returns (confirmed periods) | ✅ Live | `backend/historical_returns.py` |
| Zone History (calendar-day confirmation) | ✅ Live | `backend/main.py` |
| Dashboard (orbital hero, HR, PF, charts) | ✅ Live | `index.html` |
| X Bot (scan, generate, post) | ✅ Live | Hetzner VPS (`~/alphacycle-bot/`) |
| Stripe Integration | ⏳ Test mode | Awaiting legal structure |
| Alert Emails | ⏳ Planned | After paid tier launch |
| Snapshot Endpoint | ⚠️ Bug | `days_since_top` param missing in `build_snapshot()` |

### Locked Constants (NEVER modify):

1. **ARC Formula:** `ma_200w × 0.35 + drawdown × 0.25 + liquidity × 0.25 + fear_greed × 0.15`
2. **Zone Boundaries:** `< 30 / < 40 / < 60 / < 70` (Deep Value / Accumulation / Expansion / Risk Rising / Euphoria)
3. **ARC = "AlphaCycle Risk Composite"**

---

## 3. AI STACK ARCHITECTURE

```
┌─────────────────────────────────────────────────┐
│                   NOAH (Owner)                   │
│         Strategic decisions, final QA            │
└──────────┬──────────┬──────────┬────────────────┘
           │          │          │
    ┌──────▼──┐ ┌─────▼────┐ ┌──▼──────────┐
    │  CLAUDE  │ │  CURSOR  │ │   ChatGPT   │
    │ Strategy │ │   Code   │ │  Operating  │
    │ QA/Forge │ │ Execution│ │    Brain    │
    └──────┬──┘ └─────▲────┘ └─────────────┘
           │          │
           │  Prompts │
           └──────────┘

    ┌────────────┐ ┌───────────┐ ┌──────────┐
    │ Midjourney │ │ Perplexity│ │   Grok   │
    │  Visuals   │ │  Research │ │ X Intel  │
    └────────────┘ └───────────┘ └──────────┘
```

### Information Flow:

1. **Noah** defines goals and makes strategic decisions
2. **ChatGPT** acts as "Operating Brain" — plans, coordinates, writes specs
3. **Claude** acts as "Prompt Forge" — writes QA-reviewed Cursor prompts, audits system consistency
4. **Cursor** executes prompts on the codebase (the only agent that touches code)
5. **Midjourney** creates visual assets
6. **Perplexity** handles research
7. **Grok** provides X platform intelligence

### Critical Rule:

**Only Cursor modifies code.** Claude writes prompts FOR Cursor. ChatGPT plans and coordinates. No agent directly edits `index.html` or backend files — everything goes through Cursor prompts.

---

## 4. AGENT ROLES

### Claude (Prompt Forge)

**Primary responsibilities:**
- Write execution-ready Cursor prompts (HTML, CSS, JS, Python)
- QA review all prompts before execution
- System consistency auditing
- Product architecture decisions
- X content strategy support

**Rules for Claude:**
- Always read `DEPLOY_STATE.md` and `permanent-fixes.mdc` before writing prompts
- Never guess variable names — instruct Cursor to inspect actual code
- Every prompt must include validation checklist
- Every prompt must include git commit message
- Never change locked constants without explicit justification + backtest

**Prompt structure (mandatory):**
```
BEVOR du anfängst: Lies DEPLOY_STATE.md und permanent-fixes.mdc vollständig.
[CHANGES]
Nichts anderes ändern.
git add [files] DEPLOY_STATE.md .cursor/rules/permanent-fixes.mdc
git commit -m "[message]"
git push
```

### ChatGPT (Operating Brain)

**Primary responsibilities:**
- High-level product planning
- UX/UI specification writing
- Feature prioritization
- Cross-system coordination
- Visual design direction

**Rules for ChatGPT:**
- Specs go to Claude for prompt conversion — never directly to Cursor
- Reference `docs/alphacycle_context.md` for system state
- Do not assume what is deployed — check with Noah or Claude

### Cursor (Code Executor)

**Primary responsibilities:**
- Execute prompts from Claude exactly as written
- Read `DEPLOY_STATE.md` before every session
- Update `DEPLOY_STATE.md` and `permanent-fixes.mdc` after every change
- Commit and push after every prompt

**Rules for Cursor:**
- Deploy prompts sequentially (never multiple simultaneously)
- Verify Railway deployment between prompts
- Inspect actual code before applying changes (don't trust line numbers)
- If something is unclear in a prompt: STOP and ask, don't guess

---

## 5. DEVELOPMENT RULES

### 5.1 Deploy Protocol

```
1. Claude writes prompt (with QA review)
2. Noah approves or requests corrections
3. Prompt goes to Cursor
4. Cursor reads DEPLOY_STATE.md + permanent-fixes.mdc
5. Cursor implements changes
6. Cursor updates DEPLOY_STATE.md + permanent-fixes.mdc
7. Cursor commits + pushes
8. Noah verifies on alphacycle.app (hard refresh)
9. If broken → git revert → report to Claude
```

### 5.2 Language Rules (User-Facing Text)

| ❌ NEVER use | ✅ USE instead |
|---|---|
| BUY / SELL | EARLY CYCLE / ELEVATED RISK |
| SIGNAL | PHASE / REGIME |
| ENTRY POINT | REGIME ENTRY |
| NO ENTRY | HIGH RISK ENVIRONMENT |
| PREDICTED / DETECTED | CLASSIFIED / IDENTIFIED |
| 10/10, 6/6 (numeric claims) | "All major transitions classified" |

**Exception:** "Bottom Formation Signal" is an allowed technical indicator name.

### 5.3 CSS Rules

- Use `!important` sparingly — only to override deeply nested rules
- Always check for duplicate selectors before adding new ones
- Consolidate media query blocks — don't scatter identical breakpoints
- Test mobile (375px) after every CSS change

### 5.4 Git Rules

- PowerShell: use `;` not `&&` between commands
- Always verify correct working directory (not temp folders)
- Commit messages follow conventional commits: `feat:`, `fix:`, `style:`, `refactor:`, `docs:`

---

## 6. REPOSITORY STRUCTURE

```
alphacycle/
├── index.html                        # Single-file frontend
├── backend/
│   ├── main.py                       # FastAPI app + all endpoints
│   ├── scoring.py                    # ARC score computation
│   ├── decision_engine.py            # get_position(), allocations
│   ├── historical_returns.py         # Forward return calculations
│   ├── backtest_engine.py            # Daily backtest engine
│   ├── snapshot.py                   # X bot snapshot builder
│   ├── cycle_anchor.py              # Cycle phase logic
│   ├── fetcher.py                    # External API data fetching
│   ├── data/
│   │   └── btc_daily_kraken.csv     # Historical OHLC (3817 rows)
│   └── services/
├── docs/
│   ├── alphacycle_context.md         # System context (technical)
│   └── alphacycle_ai_operating_manual.md  # THIS FILE
├── DEPLOY_STATE.md                   # Deployment tracking
├── .cursor/
│   └── rules/
│       └── permanent-fixes.mdc      # Architectural decisions
├── requirements.txt
└── Procfile                          # Railway config
```

### External (not in repo):

```
Hetzner VPS (95.216.152.31):
~/alphacycle-bot/
├── bot.py              # Main loop (10min scan interval)
├── config.py           # API keys (env vars), tracked accounts
├── scanner.py          # Twitter API v2 tweet fetching
├── reply_engine.py     # Claude API reply generation
├── poster.py           # Twitter posting with rate limits
├── database.py         # SQLite reply tracking
└── database.db         # Local state
```

---

## 7. MASTERPROMPT SYSTEM

### What is a Masterprompt?

A masterprompt is a detailed, QA-reviewed instruction set that Cursor executes exactly. It contains:

1. **PFLICHT block** — read DEPLOY_STATE + permanent-fixes before starting
2. **Locked constraints** — what must NOT change
3. **Goal** — what the prompt achieves
4. **Implementation** — exact steps with code snippets
5. **Validation checklist** — how to verify success
6. **Deliverable** — git add/commit/push with message

### Prompt Lifecycle:

```
[Need identified] → [ChatGPT writes spec] → [Claude writes prompt]
→ [Noah QA reviews] → [Corrections applied] → [Cursor executes]
→ [Noah verifies live] → [Done or revert]
```

### QA Review Protocol:

Before any prompt is approved, check:
1. Does it reference actual class/ID names? (not guessed)
2. Does it break any locked constants?
3. Does it conflict with previously deployed changes?
4. Are there CSS specificity conflicts?
5. Does it handle mobile?
6. Does it preserve all element IDs for JS compatibility?

---

## 8. PHASE 1 OBJECTIVES (Current)

### 8.1 Immediate (Pre-Revenue)

| Priority | Task | Status |
|---|---|---|
| 1 | Hero Orbit Mobile Fix (labels, ring size, overlaps) | 🔄 In progress |
| 2 | Snapshot Bug Fix (`days_since_top`) | ⏳ Pending |
| 3 | X Bot optimization (reply quality, SKIP logic) | 🔄 In progress |
| 4 | Auth "failed to fetch" bug | ⏳ Needs investigation |

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

## 9. KNOWN ISSUES & TECH DEBT

1. **CoinCap API failing:** `FAILED https://api.coincap.io/v2/assets: [Errno -2]` — not critical, data comes from other sources
2. **`days_since_top` snapshot bug:** `build_snapshot()` doesn't accept the param
3. **Auth "failed to fetch":** Supabase connection issue — needs DevTools investigation
4. **CSS specificity wars:** Multiple `!important` overrides accumulated from iterative prompts — needs consolidation pass
5. **Landing page hardcoded values:** "+151%" and zone names need manual updates when backtest data changes

---

## 10. EMERGENCY PROCEDURES

### Site broken after deploy:

```bash
git log --oneline -10          # Find last good commit
git checkout <hash> -- index.html
git add index.html
git commit -m "revert: restore stable index.html"
git push
```

### Bot posting garbage:

```bash
ssh root@95.216.152.31
screen -r alphacycle
# Ctrl+C to stop
# Fix reply_engine.py
python3 bot.py
```

### Railway deploy stuck:

Check Railway dashboard → Deployments → latest build logs. If build fails, check `requirements.txt` for version conflicts.

---

*Last updated: 2026-04-11*
*This document is maintained by Claude (Prompt Forge) and Noah.*
*For technical system details, see `docs/alphacycle_context.md`.*

---

## Section 11 — AlphaCycle Signal Architecture

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
ARC = ma_200w × 0.35 + drawdown × 0.25 + liquidity × 0.25 + fear_greed × 0.15
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

The ARC formula and zone boundaries are **permanently locked**. They must never be modified.

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
- **Spot Allocation Range** — Percentage range (e.g., 35-50%)
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

## Section 12 — AI Agent Initialization Protocol

Every AI agent entering the AlphaCycle project must follow this initialization sequence before performing any work. This ensures consistency, prevents contradictions, and maintains system integrity across all AI-assisted workflows.

### Step 1 — Read Foundation Documents

Before any action, the agent must read and internalize:

```
REQUIRED READING:
1. docs/alphacycle_ai_operating_manual.md    — Complete system architecture and rules
2. docs/alphacycle_context.md                — Current market context and project state
```

If either document is unavailable, the agent must request it before proceeding.

### Step 2 — Identify Role

Each AI agent operates within a defined role. Roles do not overlap.

```
AGENT ROLES:
┌─────────────┬──────────────────────────────────────────────────┐
│ Agent       │ Role                                             │
├─────────────┼──────────────────────────────────────────────────┤
│ ChatGPT     │ Operating Brain — Strategy, planning, review     │
│ Claude      │ Prompt Forge — Content, prompts, architecture    │
│ Cursor      │ Code Execution — Implementation only             │
│ Midjourney  │ Visual Engine — Brand imagery                    │
│ Perplexity  │ Research — Market research, competitor analysis  │
│ Grok        │ X Intelligence — Platform-specific insights      │
└─────────────┴──────────────────────────────────────────────────┘
```

An agent must never act outside its defined role without explicit instruction from Noah.

### Step 3 — Confirm System Constraints

Before performing any work, the agent must confirm awareness of these locked constraints:

```
LOCKED — NEVER MODIFY:
├── ARC Formula: ma_200w × 0.35 + drawdown × 0.25 + liquidity × 0.25 + fear_greed × 0.15
├── ARC Zone Boundaries: 0-29 / 30-39 / 40-59 / 60-69 / 70-100
├── ARC Zone Names: Deep Value / Accumulation / Expansion / Risk Rising / Euphoria
├── ARC Component Names: Trend, Drawdown, Sentiment, Liquidity
├── ARC Full Name: AlphaCycle Risk Composite
├── Data Sources: Kraken, FRED, Alternative.me, DeFiLlama, OKX
├── Brand Voice: Structural, calm, analytical, never hypey
├── Content Rules: No $BTC, no hashtags, no emojis, no predictions
└── Product Truth: Measures risk, does not predict price
```

If any instruction conflicts with these constraints, the agent must flag the conflict and refuse to proceed until Noah resolves it.

#### Methodology Protection

AI agents may assist with analysis, explanation, or visualization.

However, AI agents are strictly prohibited from modifying the ARC methodology or introducing alternative scoring systems without explicit approval from Noah.

AlphaCycle methodology is considered locked intellectual property.

### Step 4 — Workflow Compliance

No agent modifies production code or live systems directly.

```
WORKFLOW:
1. Noah requests work
2. Planning agent (ChatGPT or Claude) designs the solution
3. Planning agent generates a Cursor implementation prompt
4. Cursor implements the code
5. Code is pushed to GitHub
6. Noah deploys via git pull on VPS
7. DEPLOY_STATE.md and permanent-fixes.mdc are updated
```

Cursor is strictly an execution engine. Cursor must never make architectural decisions or modify system logic beyond the instructions explicitly provided in the implementation prompt.

Every Cursor prompt must begin with:
```
BEVOR du anfaengst: Lies DEPLOY_STATE.md und permanent-fixes.mdc vollstaendig.
NACHDEM du fertig bist: Aktualisiere DEPLOY_STATE.md und permanent-fixes.mdc
mit allen Aenderungen dieser Session, dann:
git add DEPLOY_STATE.md .cursor/rules/permanent-fixes.mdc && git commit -m 'docs: DEPLOY_STATE update' && git push
```

No exceptions.

### Step 5 — Context Verification

Before generating any public-facing content, the agent must verify:

```
CONTENT VERIFICATION:
├── Does this reinforce AlphaCycle as Bitcoin Cycle Intelligence?
├── Does this sound like a real operator brand, not generic crypto?
├── Does this strengthen trust?
├── Does this match what the product actually does?
├── Is every claim factually consistent with current ARC data?
├── Are there maximum 2 data points (posts) or 260 characters (replies)?
└── Would the target audience (macro/cycle analysts) respect this?
```

If any check fails, the content must be revised before output.

### AI Methodology Protection

AI agents must treat the AlphaCycle methodology as protected system logic.

Agents may:

- analyze signals
- explain ARC behavior
- generate visualizations
- assist with documentation

Agents may NOT:

- redesign ARC components
- introduce alternative composites
- change signal definitions
- modify weighting structures

Any suggestion that alters the ARC methodology must be explicitly labeled as a "theoretical discussion" and cannot be implemented without Noah's approval.

---

## Section 13 — AlphaCycle Long-Term Vision

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
├── Newsletter (weekly ARC report via Beehiiv)
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
