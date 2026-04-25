# Stage 5: Entry Strategy Recommendation

Synthesize stages 1-4 into an actionable market-entry strategy.

## Inputs

Use the framing brief and all prior stage artifacts as context:

- Stage 1 foundation findings
- Stage 2 competitive findings
- Stage 3 risk findings
- Stage 4 demand validation findings

## Output Contract

Return a structured `StageOutput` object. Include exactly one Markdown artifact
in `artifacts`:

- `stage5_strategy.md`

The artifact content must include a `## Entry Strategy` section containing at
minimum:

1. **Recommended entry mode** - direct, partnership, acquisition, or hybrid;
   justify against the foundation, competitive, risk, and demand findings.
2. **12-month roadmap** - phased milestones with go/no-go gates.
3. **Resource requirements** - capital, team, partnerships needed for phase 1.
4. **Success metrics** - 3-5 KPIs and target thresholds for the first
   6 and 12 months.
5. **Top 3 risks to the recommendation** - and the mitigations.

Every factual or key claim in the artifact content MUST end with one or more
`[^src_id]` citation tokens copied from prior artifacts or returned by the
search/RAG tools. Do not use internal-only citations such as "see Foundation
section 2" as a substitute for source citations.

The `evidence` list MUST include a matching `src_id` value for every `[^src_id]`
token used in the artifact content.

End with `STAGE_COMPLETE`.
