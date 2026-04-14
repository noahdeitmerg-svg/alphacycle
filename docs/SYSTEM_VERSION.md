# AlphaCycle — System Version

---

## Current Version

```
SYSTEM VERSION: 1.3.1
DATE: 2026-04-10
UPDATED BY: Cursor (repo commit — SYSTEM_VERSION.md + README stack)
```

---

## Component Versions

| Component | Version | Last Changed |
|---|---|---|
| ARC Model | v1.2 | 2026-04-12 |
| Bot Pipeline | v2 | 2026-04-13 |
| AI Architecture | v1 | 2026-04-13 |
| Auto-Deploy | v1 | 2026-04-13 |
| Dashboard | — | ongoing |

---

## Changed Documents (this version)

| Document | Change |
|---|---|
| SYSTEM_VERSION.md | Added to repo; canonical system version + agent init step 5 |
| README.md | Mandatory reading list 7 → 8 docs (SYSTEM_VERSION after SYSTEM_STATE) |
| SYSTEM_STATE.md | Stack count and doc table aligned with README |
| permanent-fixes.mdc | AI Knowledge Stack includes SYSTEM_VERSION.md |
| TASK_PIPELINE.md | T-001 status line: seven-doc → eight-doc stack |
| DEPLOY_STATE.md | Session logged |

---

## Changed Documents (baseline 1.3 — 2026-04-13)

| Document | Change |
|---|---|
| SYSTEM_TRUTH.md | ARC v1.2 weights (35/30/15/20) |
| AI_AGENT_MASTERPROMPTS.md | 6 agents validated, v1.2 lock |
| AI_AGENT_ROLES.md | Expanded from 4 to 6 agents |
| AI_MASTER_PROMPT.md | Document Sync Protocol added |
| SYSTEM_STATE.md | T-001, T-002, Bot Pipeline, Auto-Deploy marked deployed |
| TASK_PIPELINE.md | Execution order updated, completed tasks logged |
| DEPLOY_STATE.md | 4 new deploy entries |

---

## Agent Initialization Rule

Before performing any task, every agent must:

```
1. Load docs/SYSTEM_TRUTH.md
2. Load docs/AI_MASTER_CONTEXT.md
3. Load docs/AI_AGENT_MASTERPROMPTS.md (your section)
4. Load docs/SYSTEM_STATE.md
5. Load docs/SYSTEM_VERSION.md (this file)
6. State: "System version 1.3.1 confirmed. ARC v1.2."
7. Load DEPLOY_STATE.md
8. Wait for task
```

If the agent's version does not match this file: stop and request updated documents from Noah.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.3.1 | 2026-04-10 | SYSTEM_VERSION.md in repo; README 8-doc stack; SYSTEM_STATE + permanent-fixes aligned |
| 1.3 | 2026-04-13 | ARC v1.2, Hi/Lo Engine, Auto-Deploy, Bot Pipeline v2, AI Architecture (6 agents, 8 docs) |
| 1.2 | 2026-04-12 | ARC weights updated (25/25→30/15), backtest engine cleaned, zone boundaries normalized |
| 1.1 | 2026-04-10 | Display transform k=0, reply prompt v2, docs structure created |
| 1.0 | 2026-03-18 | Initial system: ARC v1.0, dashboard, X bot, basic docs |

---

## Version Bump Rules

- **Patch (1.3 → 1.3.1):** Doc updates, typo fixes, task status changes
- **Minor (1.3 → 1.4):** New features deployed, infrastructure changes, agent role changes
- **Major (1.3 → 2.0):** ARC methodology change, fundamental architecture redesign

Every Cursor commit that modifies files in `docs/` must bump the version and update this file.

---

*This file is the single source of truth for system version.*
