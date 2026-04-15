# AlphaCycle — Task Pipeline
# Active and planned tasks across all agents

> **Updated after every completed task.**
> **New chats: read this to understand what is in progress and what comes next.**

---

## EXECUTION ORDER

Tasks must be deployed in this order. Each task completes before the next begins.

```
QUEUE:
  T-001 (DONE) → T-002 → T-003 → T-004 → T-005 → T-006 → T-007
```

---

## ACTIVE TASKS

### T-001 — ARC v1.2 Weight Deploy
| Field | Value |
|---|---|
| Priority | 🔴 CRITICAL |
| Owner | Quant Research (validated) |
| Executor | Cursor Builder |
| Status | **DEPLOYED** (2026-04-12) — verify prod + T-007 |
| Description | Change ARC weights: drawdown 0.25→0.30, liquidity 0.25→0.15, sentiment 0.15→0.20. Version bump 1.0→1.2. |
| Affected Files | `backend/arc_config.py`, `backend/scoring.py`, `backend/services/backtest_engine.py`, `index.html`, `docs/SYSTEM_TRUTH.md`, `docs/AI_MASTER_CONTEXT.md`, `.cursor/rules/permanent-fixes.mdc`, `DEPLOY_STATE.md` |
| Risk | All ARC scores change. Historical Returns, Track Record, Landing Page hardcoded values need post-deploy verification. |
| Post-Deploy | Verify /api/historical-returns, #track-dv-return vs zones.deep_value.avg_12m, landing event cards, ARC Chart zone bands. |
| Prompt Location | Session 5 transcript — full prompt with 8 files + backtest_engine.py hardcoded weight fix |

---

### T-002 — Hi/Lo Engine Deploy
| Field | Value |
|---|---|
| Priority | 🔴 CRITICAL |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | PROMPT READY — not deployed (verified via ZIP) |
| Description | Live ARC must use daily OHLC (high/low) for parity with backtest. Currently all compute_arc_score() calls pass weekly_high=None, weekly_low=None. |
| Affected Files | `backend/fetcher.py` (new function fetch_kraken_ohlc_latest), `backend/main.py` (refresh_cache, /api/arc-summary, /api/history-daily, /api/backtest, _save_today_snapshot) |
| Risk | If Kraken OHLC fails, fallback to close-only. Graceful degradation. |
| Prompt Location | Session 5 transcript — 6-step prompt |

---

### T-003 — Hero Orbit Label Fix
| Field | Value |
|---|---|
| Priority | 🟡 MEDIUM |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | PROMPT READY |
| Description | Labels must sit at zone midpoints on the conic gradient ring. Right-side labels use left:108%, left-side use right:108%. Text extends away from ring. Dot z-index above labels. |
| Affected Files | `index.html` (CSS only — .orbit-label, .ol-dv through .ol-eu, mobile media queries) |
| Risk | Low — CSS only, no JS or backend. |
| Prompt Location | Session 5 transcript — mathematically calculated positions |

---

### T-004 — UX Overhaul
| Field | Value |
|---|---|
| Priority | 🟡 MEDIUM |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | PROMPT READY |
| Description | Fix Signal Summary JS override (renderSignalSummary sets display:block), hide Risk/Reward Profile (dec-layer-3), compact Positioning Framework, improve text readability, reduce hero spacing. |
| Affected Files | `index.html` (CSS + JS — renderSignalSummary, .dec-layer-3, .decision-note, #hero-regime-context, spacing rules) |
| Risk | Low — mostly CSS. JS change to renderSignalSummary is minimal (function body replacement). |
| Prompt Location | Session 5 transcript — 6-point refinement prompt |

---

### T-005 — Orbit Ring Clarity
| Field | Value |
|---|---|
| Priority | 🟡 MEDIUM |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | PROMPT READY |
| Description | Ring gradient barely visible (mask too tight), labels need permanent zone colors, context text too long, inner ring too prominent. |
| Affected Files | `index.html` (CSS — .orbit-ring::before mask, .ol-* colors, _getCycleDescription JS function, .orbit-inner-ring) |
| Risk | Low — CSS + 1 small JS function. |
| Prompt Location | Session 5 transcript — ring clarity prompt |

---

### T-006 — Docs Consolidation
| Field | Value |
|---|---|
| Priority | 🟢 LOW |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | **PARTIAL** — README eight-doc stack (+ `SYSTEM_VERSION.md`) + `AI_AGENT_MASTERPROMPTS` / `SYSTEM_STATE` / `TASK_PIPELINE` live; full legacy delete/merge deferred until explicit approval |
| Description | Consolidate 9 documentation files into 4. Merge operating manual + context + sections 11-13 into AI_MASTER_CONTEXT. Merge CURSOR_MASTERPROMPT into AI_MASTER_PROMPT appendix. Add AI_AGENT_MASTERPROMPTS.md. Delete 5 redundant files. |
| Affected Files | `docs/` (all files), `README.md`, `DEPLOY_STATE.md`, `permanent-fixes.mdc` |
| Risk | No code impact. Documentation only. |
| Delete | alphacycle_ai_operating_manual.md, alphacycle_ai_operating_manual_COMPLETE.md, AlphaCycle-AI-Manual-Sections-11-13-FINAL-v2.md, alphacycle_context.md, CURSOR_MASTERPROMPT.md (root) |
| Prompt Location | Session 5 transcript — 7-step consolidation prompt |

---

### T-007 — Post-Deploy Value Verification
| Field | Value |
|---|---|
| Priority | 🟡 MEDIUM (after T-001) |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | **READY** (T-001 deployed — run verification pass) |
| Description | After ARC v1.2 deploy: verify and fix hardcoded values. Track highlight Deep Value 12M (+236.4% per API), landing narrative numbers if policy changes, any zone-dependent display text. |
| Affected Files | `index.html` (hardcoded strings), potentially `backend/snapshot.py` |
| Risk | Medium — wrong numbers visible to users. |

---

## BACKLOG (not yet prioritized)

### T-008 — Zone History Data Fix
| Field | Value |
|---|---|
| Priority | 🔵 BACKLOG |
| Owner | Quant Research |
| Executor | Cursor Builder |
| Status | NOT STARTED |
| Description | Zone History shows "Expansion for 58 weeks" but live ARC is Accumulation/Deep Value. Confirmation logic may need adjustment, or the backtest data needs re-evaluation after v1.2. |
| Affected Files | `backend/main.py` (compute_zone_history, /api/zone-history) |
| Dependency | T-001 (v1.2 will change all historical scores — zone history may self-correct) |

---

### T-009 — CSS Consolidation Pass
| Field | Value |
|---|---|
| Priority | 🔵 BACKLOG |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | NOT STARTED |
| Description | Multiple !important overrides accumulated from iterative prompts. Consolidate duplicate selectors, remove conflicting rules, unify media query blocks. |
| Affected Files | `index.html` (CSS sections) |

---

### T-010 — LLC Formation + Stripe Live
| Field | Value |
|---|---|
| Priority | 🔴 CRITICAL (revenue blocker) |
| Owner | Noah (manual) |
| Executor | Noah |
| Status | BLOCKED — Noah action item |
| Description | Form US LLC (Wyoming, ~$150, 1-2 weeks). Then activate Stripe Live mode. Then launch paid tier ($49/mo, 7-day trial). |
| Affected Files | Stripe dashboard (not code) |

---

### T-011 — Alert Emails (Resend)
| Field | Value |
|---|---|
| Priority | 🔵 BACKLOG |
| Owner | Operating Brain |
| Executor | Cursor Builder |
| Status | PLANNED — after revenue |
| Description | Zone change notifications for paid users via Resend email service. |
| Affected Files | `backend/main.py` (new endpoint), Resend API integration |

---

### T-012 — Snapshot days_since_top Fix
| Field | Value |
|---|---|
| Priority | 🟢 LOW |
| Owner | Prompt Forge |
| Executor | Cursor Builder |
| Status | RESOLVED per alphacycle_context.md (build_snapshot accepts param, main.py passes it) |
| Description | Was: build_snapshot() didn't accept days_since_top. Now resolved in recent deploy. |
| Affected Files | None (already fixed) |

---

### T-013 — Bot Self-Learning System
| Field | Value |
|---|---|
| Priority | 🔵 BACKLOG |
| Owner | Prompt Forge (architecture) + Growth Engine (thresholds) |
| Executor | Cursor Builder |
| Status | PLANNED — implement after 200+ followers |
| Description | Store replies + engagement metrics, score replies (likes×1 + replies×2 + reposts×3), rotate top examples into reply prompt dynamically. |
| Affected Files | `alphacycle-x-bot/learning_engine.py` (neu), `growth_engine.py`, `prompts/reply_system.txt`, `database.py` |
| Dependency | 200+ followers (engagement data meaningless below that) |
| Blocker | X API rate limits on Free Tier (100 reads/mo) |

---

## COMPLETED TASKS (recent)

| ID | Task | Date | Commit |
|---|---|---|---|
| C-001 | Zone Boundary Normalization (<=29 → <30) | 2026-04-12 | aec5525 |
| C-002 | Deprecated Backtest Removal | 2026-04-12 | ac7589a |
| C-003 | ARC Source Purity | 2026-04-12 | f5ddd21 |
| C-004 | Supabase Resume + Keep-Alive Cronjob | 2026-04-12 | — (infra) |
| C-005 | AI Knowledge Stack (context.md, operating manual) | 2026-04-11 | ab417c0 |
| C-006 | Reply Engine Prompt Update (180 chars, shorter examples) | 2026-04-12 | — (VPS) |
| C-007 | Docs structure (docs/ folder + README reference) | 2026-04-11 | ab417c0 |
| C-008 | Reply system prompt v2 (70/30 rule, rotation) | 2026-04-10 | fb082f7 |
| C-009 | ARC v1.2 weights in code + UI + docs | 2026-04-12 | see DEPLOY_STATE |
| C-010 | X-bot config sync (keywords, 41 accounts, defaults) | 2026-04-14 | ed13483 |
| C-011 | X-bot Tier 1: +NoLimitGains; 42 tracked (11+16+15) | 2026-04-14 | 7b1ebd8 |
| C-012 | Reply System v3: Opus + reply/QA prompts + QA pattern retries | 2026-04-14 | 194447c |

**C-011 / Prompt FIX 5A — validation**

- [x] `len(TRACKED_ACCOUNTS) == 42` (11 + 16 + 15; Tier 1 inkl. NoLimitGains)

**C-012 / QA — validation**

- [x] `qa_system.txt`: **13** Regeln (letzte = **repetitive_opener**, **KEIN** analyst_test / `not_analyst_grade`)

---

## TASK FLOW DIAGRAM

```
            ┌─────────────────────────────────────────┐
            │           TASK LIFECYCLE                 │
            │                                         │
            │  BACKLOG → PLANNED → PROMPT READY →     │
            │  QA APPROVED → DEPLOYING → DEPLOYED →   │
            │  VERIFIED → COMPLETED                   │
            └─────────────────────────────────────────┘

Status definitions:
  BACKLOG       — Identified, not yet planned
  PLANNED       — Assigned to owner, design in progress
  PROMPT READY  — Cursor prompt written by Prompt Forge
  QA APPROVED   — QA Review has approved the prompt
  DEPLOYING     — Cursor Builder is executing
  DEPLOYED      — Code pushed, Railway building
  VERIFIED      — Noah confirmed on alphacycle.app
  COMPLETED     — Moved to completed table
  BLOCKED       — Waiting on dependency or external action
```

---

*Last updated: 2026-04-14*
*Next update: after T-002 prompt execution or T-007 verification*
