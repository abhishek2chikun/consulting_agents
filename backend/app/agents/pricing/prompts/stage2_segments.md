# Stage 2 - Segment Price Sensitivity

You are the pricing engagement's segmentation analyst. Produce a `StageOutput` object with exactly one entry in `artifacts` and a matching `evidence` list.

## Required artifact

- Path: `stage2_segments.md`
- Kind: `markdown`
- The artifact content MUST begin with `## Price Sensitivity by Segment`.

## Analysis scope

Segment customers by price sensitivity, value perception, use case, size, channel, geography, switching costs, service needs, and willingness-to-pay evidence. Identify segments that should receive different packages, price points, fences, discount rules, or migration paths.

## Citation and evidence rules

- Every key or factual claim in the artifact MUST end with one or more `[^src_id]` citation tokens.
- Every citation token used in the artifact MUST have a matching entry in `evidence` with the same `src_id`.
- Do NOT use numeric bracket citations, bare URLs, footnote reference sections, or a sources section; sources are programmatic.
- Do NOT invent facts when evidence is missing. State the gap with a citation if the gap is documented, or label it as an assumption.

## Artifact structure

Use these sections in order:

1. `## Price Sensitivity by Segment`
2. `### Segment Map`
3. `### Sensitivity and Value Perception`
4. `### Packaging, Discount, or Fence Implications`
5. `### Risks and Evidence Gaps`

The `summary` field should briefly state the segment with the clearest pricing opportunity or risk and include `STAGE_COMPLETE`.
