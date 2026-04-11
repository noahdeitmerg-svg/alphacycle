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
