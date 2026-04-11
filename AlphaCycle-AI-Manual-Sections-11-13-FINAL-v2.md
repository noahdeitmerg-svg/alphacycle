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
