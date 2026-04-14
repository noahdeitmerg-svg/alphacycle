# AlphaCycle — System State
# Current snapshot for AI agent continuity

> **Read after SYSTEM_TRUTH.md and AI_MASTER_CONTEXT.md.**
> **This file is updated after every significant deploy or architecture decision.**

---

## 1. CURRENT DEVELOPMENT PHASE

```
Phase: PRE-REVENUE
Stage: Product refinement + growth foundation
```

AlphaCycle is live at https://alphacycle.app with a functional dashboard, ARC engine, and X bot. Revenue activation is blocked by legal structure (US LLC). Current focus is product polish, growth, and AI system architecture.

| Milestone | Status |
|---|---|
| ARC Engine (v1.2) | ✅ Deployed in repo (Railway follows main) |
| Dashboard (orbital hero, HR, PF, charts) | ✅ Live, UX refinements pending |
| X Bot (scan, reply, daily posts) | ✅ Live on Hetzner VPS |
| Telegram Approval System | ✅ Live |
| Stripe Integration | ⏳ Test mode (awaiting LLC) |
| AI Knowledge Stack | ✅ README mandatory list: 8 documents |
| AI Agent System | ✅ 6 agents defined with masterprompts |
| Supabase Auth | ✅ Live (free tier, cronjob keep-alive) |
| Alert Emails | ⏳ Planned (post-revenue) |

---

## 2. ACTIVE TASKS

Authoritative queue with IDs, owners, and file paths: **`docs/TASK_PIPELINE.md`**.  
High level: **T-002** Hi/Lo Engine next; **T-007** post-deploy value checks unblocked after **T-001** (ARC v1.2) shipped.

---

## 3. KNOWN ISSUES

| # | Issue | Severity | Workaround |
|---|---|---|---|
| 1 | Zone History data mismatch — confirmed zone "Expansion" but live ARC is Deep Value/Accumulation | Medium | Section hidden via CSS |
| 2 | CSS specificity accumulation — multiple !important overrides from iterative prompts | Low | Works but fragile |
| 3 | Orbit labels may overlap ring on some viewports | Low | Prompt written, not deployed |
| 4 | Landing / timeline use **event** forward returns (+170%, +95%); Track highlight #track-dv-return must track zones.deep_value.avg_12m | Low | #track-dv-return synced 2026-04-10 (+236.4%) |
| 5 | Signal Summary JS override — renderSignalSummary() sets display:block | Low | CSS !important wins, but JS should be disabled |
| 6 | Risk/Reward Profile (dec-layer-3) still renders | Low | Prompt written to hide |
| 7 | CoinCap API failing (ERR_NAME_NOT_RESOLVED) | None | Non-critical, data from other sources |

---

## 4. INFRASTRUCTURE

| Service | Purpose | Status | Notes |
|---|---|---|---|
| Railway | Backend (FastAPI) | ✅ Running | Auto-deploy on git push |
| GitHub | Repository | ✅ Active | Main branch, direct push |
| Supabase | Auth + DB | ✅ Running | Free tier, cronjob keep-alive every 5 days |
| Stripe | Payments | ⏳ Test mode | $49/mo, 7-day trial — awaiting LLC |
| Hetzner VPS | X Bot + Telegram | ✅ Running | 95.216.152.31, screen sessions: xbot + tg |
| Kraken API | BTC/ETH OHLC | ✅ Active | Primary price source |
| FRED API | WALCL, TGA, RRP | ✅ Active | Weekly (Thursday), 3-7 day lag |
| Alternative.me | Fear & Greed | ✅ Active | Daily |
| OKX | Funding rates | ✅ Active | Replaced Binance/Bybit (403 on Railway) |

### Supabase Keep-Alive
```
Cronjob on Hetzner VPS (crontab -e):
0 8 */5 * * curl -s https://epcvkgtneeafgpjjrfiq.supabase.co/rest/v1/ -H "apikey: ANON_KEY" > /dev/null 2>&1
```

### VPS Bot Management
```bash
ssh root@95.216.152.31
cd ~/alphacycle-repo/alphacycle-x-bot
./restart-screens.sh     # restarts xbot + tg screens
screen -r xbot           # attach to bot
screen -r tg             # attach to telegram listener
```

---

## 5. AI SYSTEM STATUS

### Agent Registry

| Agent | Tool | Status | Current Chat |
|---|---|---|---|
| Operating Brain | ChatGPT | ✅ Defined | Active |
| Prompt Forge | Claude | ✅ Defined | Active (this session) |
| Quant Research | Claude/ChatGPT | ✅ Defined | Active |
| QA Review | Claude | ✅ Defined | Active |
| Growth Engine | Claude | ✅ Defined | Active |
| Cursor Builder | Cursor | ✅ Defined | Ready |

### Documentation Stack

| Document | Path | Status |
|---|---|---|
| SYSTEM_TRUTH.md | docs/ | ✅ Canon (ARC v1.2 aligned) |
| AI_MASTER_CONTEXT.md | docs/ | ✅ Canon |
| AI_AGENT_ROLES.md | docs/ | ✅ Canon |
| AI_MASTER_PROMPT.md | docs/ | ✅ Canon |
| AI_AGENT_MASTERPROMPTS.md | docs/ | ✅ Six agents, full prompts |
| SYSTEM_STATE.md | docs/ | ✅ This file |
| SYSTEM_VERSION.md | docs/ | ✅ Version SSOT (see README order) |
| TASK_PIPELINE.md | docs/ | ✅ Task IDs and status |

### Legacy / optional docs
Long-form manuals (e.g. `alphacycle_ai_operating_manual_COMPLETE.md`) may remain under `docs/` for human deep-dive; **onboarding order** is always the eight files in root `README.md` — no second “truth” file may contradict `SYSTEM_TRUTH.md`.

---

## 6. LAST ARCHITECTURE DECISION

**ARC v1.2 Weight Update (2026-04-12)**

```
BEFORE: trend=0.35  drawdown=0.25  liquidity=0.25  sentiment=0.15
AFTER:  trend=0.35  drawdown=0.30  liquidity=0.15  sentiment=0.20
```

- Quant Research validated against 11 cycle events
- 4/4 Tops in Euphoria (was 3/4 — Nov 2021 fixed)
- 3/3 Bottoms deeper in Deep Value
- Neutral phase drift: max ±2.2 points
- Deployed in codebase **2026-04-12** (see `DEPLOY_STATE.md`).

---

## 7. NEXT PRIORITY (ordered)

```
1. Deploy Hi/Lo Engine (T-002 — live/chart parity)
2. Deploy Hero Orbit label fix (T-003)
3. Deploy UX Overhaul (T-004)
4. Post-deploy verification (T-007 — hardcoded %, HR, landing)
5. Docs consolidation / deletions (T-006 — only when explicitly approved)
6. LLC formation (Noah action item) → Stripe Live → Revenue
```

---

## 8. ARC CURRENT READING

| Field | Value | Source |
|---|---|---|
| ARC Score | ~27-35 (Deep Value / Accumulation) | /api/arc-summary |
| BTC Price | ~$71,000 | Kraken |
| Fear & Greed | ~16 (Extreme Fear) | Alternative.me |
| Cycle Phase | Late Bear | cycle_anchor |
| Days Since Top | ~186 | cycle_anchor |

*Note: These values change daily. Query /api/arc-summary for current data.*

---

*Last updated: 2026-04-14*
*Next update: after T-002 deploy or major infra change*
