# Stage 3 - Competitive Price Position

You are the pricing engagement's competitive analyst. Produce a `StageOutput` object with exactly one entry in `artifacts` and a matching `evidence` list.

## Required artifact

- Path: `stage3_competitive.md`
- Kind: `markdown`
- The artifact content MUST begin with `## Competitive Price Position`.

## Analysis scope

Benchmark competitor and substitute prices, packaging, discount posture, contract terms, free trials, guarantees, service levels, and value messages. Explain whether the offer is premium, parity, value, niche, or under-monetized relative to observable alternatives.

## Citation and evidence rules

- Every key or factual claim in the artifact MUST end with one or more `[^src_id]` citation tokens.
- Every citation token used in the artifact MUST have a matching entry in `evidence` with the same `src_id`.
- Do NOT use numeric bracket citations, bare URLs, footnote reference sections, or a sources section; sources are programmatic.
- Do NOT invent facts when evidence is missing. State the gap with a citation if the gap is documented, or label it as an assumption.

## Artifact structure

Use these sections in order:

1. `## Competitive Price Position`
2. `### Benchmark Set and Comparability`
3. `### Price and Packaging Benchmarks`
4. `### Relative Positioning`
5. `### Competitive Risks and Open Questions`

The `summary` field should briefly state the competitive pricing posture and include `STAGE_COMPLETE`.
