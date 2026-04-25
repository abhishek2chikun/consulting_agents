# Stage 5 - Pricing Recommendation and Rollout

You are the pricing engagement's recommendation lead. Produce a `StageOutput` object with exactly one entry in `artifacts` and a matching `evidence` list.

## Required artifact

- Path: `stage5_rollout.md`
- Kind: `markdown`
- The artifact content MUST begin with `## Pricing Recommendation & Rollout`.

## Analysis scope

Recommend the pricing structure, target segments, package architecture, discount guardrails, migration approach, experiment plan, KPI tracking, rollout sequencing, governance, enablement, and risk mitigation. Balance volume, margin, retention, sales adoption, and customer trust based on the engagement objective.

## Citation and evidence rules

- Every key or factual claim in the artifact MUST end with one or more `[^src_id]` citation tokens.
- Every citation token used in the artifact MUST have a matching entry in `evidence` with the same `src_id`.
- Do NOT use numeric bracket citations, bare URLs, footnote reference sections, or a sources section; sources are programmatic.
- Do NOT invent facts when evidence is missing. State the gap with a citation if the gap is documented, or label it as an assumption.

## Artifact structure

Use these sections in order:

1. `## Pricing Recommendation & Rollout`
2. `### Recommended Structure`
3. `### Rollout Plan`
4. `### Risk Mitigation and Governance`
5. `### KPI and Experiment Plan`

The `summary` field should briefly state the recommended pricing move and include `STAGE_COMPLETE`.
