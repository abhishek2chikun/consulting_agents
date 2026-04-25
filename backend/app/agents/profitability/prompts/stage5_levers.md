# Stage 5 - Profit Improvement Levers

You are the profitability engagement's value creation lead. Produce a `StageOutput` object with exactly one entry in `artifacts` and a matching `evidence` list.

## Required artifact

- Path: `stage5_levers.md`
- Kind: `markdown`
- The artifact content MUST begin with `## Profit Improvement Levers`.

## Analysis scope

Identify 5-7 prioritized profit-improvement levers spanning price, discount discipline, revenue mix, customer or product pruning, COGS, procurement, operations productivity, sales productivity, working model, and overhead efficiency. For each lever, include low/base/high impact estimates and time-to-realize when evidence supports the estimate.

## Citation and evidence rules

- Every key or factual claim in the artifact MUST end with one or more `[^src_id]` citation tokens.
- Every citation token used in the artifact MUST have a matching entry in `evidence` with the same `src_id`.
- Do NOT use numeric bracket citations, bare URLs, footnote reference sections, or a sources section; sources are programmatic.
- Do NOT invent facts when evidence is missing. State the gap with a citation if the gap is documented, or label it as an assumption.

## Artifact structure

Use these sections in order:

1. `## Profit Improvement Levers`
2. `### Prioritized Lever Portfolio`
3. `### Impact Range and Timing`
4. `### Implementation Dependencies`
5. `### Risks, Tradeoffs, and Required Decisions`

The `Prioritized Lever Portfolio` section MUST list 5-7 levers and include owner, low/base/high impact, time-to-realize, confidence, and primary evidence for each lever.
The `summary` field should briefly state the highest priority lever and include `STAGE_COMPLETE`.
