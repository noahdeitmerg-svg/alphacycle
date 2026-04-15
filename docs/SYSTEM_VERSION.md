# AlphaCycle — System Version

---

## Current Version

```
SYSTEM VERSION: 1.3.2
DATE: 2026-04-14
UPDATED BY: Cursor Builder
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
| AI_AGENT_MASTERPROMPTS.md | QA section synced to 14-rule system (repetitive opener) |
| AI_MASTER_CONTEXT.md | X-bot scan/limits updated to 41 accounts and current defaults |
| SYSTEM_STATE.md | Snapshot timestamp refreshed |
| TASK_PIPELINE.md | Added C-010 completion and refreshed update timestamp |
| SYSTEM_VERSION.md | Patch bump to 1.3.1 (this file) |

---

## Agent Initialization Rule

Before performing any task, every agent must:

```
1. Load docs/SYSTEM_TRUTH.md
2. Load docs/AI_MASTER_CONTEXT.md
3. Load docs/AI_AGENT_MASTERPROMPTS.md (your section)
4. Load docs/SYSTEM_STATE.md
5. Load docs/SYSTEM_VERSION.md (this file)
6. State: "System version 1.3.2 confirmed. ARC v1.2."
7. Load DEPLOY_STATE.md
8. Wait for task
```

If the agent's version does not match this file: stop and request updated documents from Noah.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.3.2 | 2026-04-14 | X-bot: NoLimitGains in Tier 1; 42 tracked accounts; docs + permanent-fixes sync |
| 1.3.1 | 2026-04-14 | Docs sync patch: QA rule count, X-bot account/limit references, pipeline/state refresh |
| 1.3 | 2026-04-13 | ARC v1.2, Hi/Lo Engine, Auto-Deploy, Bot Pipeline v2, AI Architecture (6 agents, 8 docs) |
| 1.2 | 2026-04-12 | ARC weights updated (25/25→30/15), backtest engine cleaned, zone boundaries normalized |
| 1.1 | 2026-04-10 | Display transform k=0, reply prompt v2, docs structure created |
| 1.0 | 2026-03-18 | Initial system: ARC v1.0, dashboard, X bot, basic docs |

---

## Version Bump Rules

- **Patch (1.3.1 → 1.3.2):** Doc updates, typo fixes, task status changes
- **Minor (1.3 → 1.4):** New features deployed, infrastructure changes, agent role changes
- **Major (1.3 → 2.0):** ARC methodology change, fundamental architecture redesign

Every Cursor commit that modifies files in `docs/` must bump the version and update this file.

---

*This file is the single source of truth for system version.*
