# AlphaCycle — System Version

---

## Current Version

```
SYSTEM VERSION: 1.3
DATE: 2026-04-13
UPDATED BY: Prompt Forge → Cursor Builder
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
| SYSTEM_TRUTH.md | ARC v1.2 weights (35/30/15/20) |
| AI_AGENT_MASTERPROMPTS.md | 6 agents validated, v1.2 lock |
| AI_AGENT_ROLES.md | Expanded from 4 to 6 agents |
| AI_MASTER_PROMPT.md | Document Sync Protocol added |
| SYSTEM_STATE.md | T-001, T-002, Bot Pipeline, Auto-Deploy marked deployed |
| TASK_PIPELINE.md | Execution order updated, completed tasks logged |
| DEPLOY_STATE.md | 4 new deploy entries |
| SYSTEM_VERSION.md | Created (this file) |

---

## Agent Initialization Rule

Before performing any task, every agent must:

```
1. Load docs/SYSTEM_TRUTH.md
2. Load docs/AI_MASTER_CONTEXT.md
3. Load docs/AI_AGENT_MASTERPROMPTS.md (your section)
4. Load docs/SYSTEM_STATE.md
5. Load docs/SYSTEM_VERSION.md (this file)
6. State: "System version 1.3 confirmed. ARC v1.2."
7. Load DEPLOY_STATE.md
8. Wait for task
```

If the agent's version does not match this file: stop and request updated documents from Noah.

---

## Version History

| Version | Date | Changes |
|---|---|---|
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
