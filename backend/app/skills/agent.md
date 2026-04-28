# app.skills — agent.md

## Status
**Active (V1.6).** Hosts the consulting skill-pack library consumed by
`app.agents._engine.skills`. V1.6 ships 20 packs total: 16 pre-existing
consulting packs plus 4 new packs (`market-sizing`,
`evidence-discipline`, `unit-economics`, `competitive-intelligence`).

---

## Purpose

`app.skills/<slug>/SKILL.md` files are prompt assets, not executable
code. The shared consulting engine loads them on demand, strips YAML
frontmatter, and prepends the bodies to system prompts for framing,
main stage prompts, stage workers, reviewers, synthesis, and audit.

The goal is to keep domain guidance versioned, reusable, and profile-
driven rather than hard-coding long frameworks into each prompt.

---

## Directory Structure
```text
app/skills/
  agent.md
  change-management/SKILL.md
  client-deliverables/SKILL.md
  competitive-intelligence/SKILL.md
  due-diligence/SKILL.md
  engagement-pricing/SKILL.md
  engagement-setup/SKILL.md
  evidence-discipline/SKILL.md
  financial-modeling/SKILL.md
  implementation-planning/SKILL.md
  market-sizing/SKILL.md
  org-design/SKILL.md
  process-excellence/SKILL.md
  project-closeout/SKILL.md
  project-governance/SKILL.md
  proposal-development/SKILL.md
  strategic-analysis/SKILL.md
  thought-leadership/SKILL.md
  unit-economics/SKILL.md
  workshop-facilitation/SKILL.md
  writing-style/SKILL.md
```

### Corresponding Tests
```text
backend/tests/unit/test_v16_skill_packs.py
backend/tests/unit/test_skill_loader.py
backend/tests/unit/test_profile_extensions.py
backend/tests/integration/test_per_stage_reviewer.py
backend/tests/integration/test_*_v16_smoke.py
```

---

## Public API

There is no direct runtime API in this package. Consumers go through:

```python
from app.agents._engine.skills import load_skill, render_skills_block, inject_skills
```

---

## V1.6 Assignments

### Profile-wide
- Framing:
  `strategic-analysis` for all three live consulting types.
- Synthesis:
  `client-deliverables`, `writing-style`.
- Audit:
  `due-diligence`, `evidence-discipline`.

### market_entry
- `stage1_foundation`: `strategic-analysis`, `market-sizing`
- `stage2_competitive`: `strategic-analysis`, `competitive-intelligence`
- `stage3_risk`: `due-diligence`, `evidence-discipline`
- `stage4_demand`: `market-sizing`, `evidence-discipline`
- `stage5_strategy`: `strategic-analysis`, `implementation-planning`

### pricing
- `stage1_value`: `strategic-analysis`, `evidence-discipline`
- `stage2_segments`: `strategic-analysis`, `market-sizing`
- `stage3_competitive`: `competitive-intelligence`, `engagement-pricing`
- `stage4_models`: `engagement-pricing`, `financial-modeling`
- `stage5_rollout`: `implementation-planning`, `change-management`

### profitability
- `stage1_revenue`: `financial-modeling`, `market-sizing`
- `stage2_cost`: `financial-modeling`, `process-excellence`
- `stage3_margin`: `financial-modeling`, `unit-economics`
- `stage4_competitor`: `competitive-intelligence`, `evidence-discipline`
- `stage5_levers`: `strategic-analysis`, `implementation-planning`

---

## Current Progress

- Skill loading is cached and deterministic via
  `app.agents._engine.skills.load_skill()`.
- Main stage, worker, reviewer, framing, synthesis, and audit prompts
  can all receive injected skill blocks.
- The 4 new V1.6 packs close evidence/market-sizing/unit-economics /
  competitor-fabrication gaps identified in the forensic pass.

## Known Issues / Blockers

- Skill assignment is profile-driven and static. There is no runtime UI
  for enabling/disabling packs per run.
- Cache invalidation is process-local; editing a `SKILL.md` requires a
  process restart to affect already-running app instances.
