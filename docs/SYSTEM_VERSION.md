# AlphaCycle — System Version

---

## Current Version

```
SYSTEM VERSION: 1.3.3
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
| alphacycle-x-bot/config.py | Reply System v3: `CLAUDE_MODEL` = Opus **claude-opus-4-6**; `RELEVANT_KEYWORDS` list refresh |
| alphacycle-x-bot/prompts/reply_system.txt | Reply System v3: STEP 1-4, angles A-G, examples, historical facts, banned words |
| alphacycle-x-bot/prompts/qa_system.txt | QA v3: 14 rules incl. **not_analyst_grade** |
| alphacycle-x-bot/growth_engine.py | QA retry: pattern switch + fixed angle hint; removed unused `_build_qa_replacement_guide` |
| AI_MASTER_CONTEXT.md | X-bot table: Primary Claude Opus + Haiku QA |
| TASK_PIPELINE.md | C-012 Reply System v3 |
| DEPLOY_STATE.md | Session + Opus cost warning for Noah |
| .cursor/rules/permanent-fixes.mdc | Reply v3 / Opus cost NEVER/ALWAYS |
| SYSTEM_VERSION.md | Patch bump to 1.3.3 (this file) |

---

## Agent Initialization Rule

Before performing any task, every agent must:

```
1. Load docs/SYSTEM_TRUTH.md
2. Load docs/AI_MASTER_CONTEXT.md
3. Load docs/AI_AGENT_MASTERPROMPTS.md (your section)
4. Load docs/SYSTEM_STATE.md
5. Load docs/SYSTEM_VERSION.md (this file)
6. State: "System version 1.3.3 confirmed. ARC v1.2."
7. Load DEPLOY_STATE.md
8. Wait for task
```

If the agent's version does not match this file: stop and request updated documents from Noah.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.3.3 | 2026-04-14 | X-bot Reply System v3: Opus primary model, new reply/QA prompts, QA pattern-only retries |
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
