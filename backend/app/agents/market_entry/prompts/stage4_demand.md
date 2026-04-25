# Stage 4: Demand Validation

You are conducting market-entry research for the objective and target market
defined in the framing brief. Stages 1-3 have produced foundation, competitive,
and risk findings; your task in this stage is to validate end-customer demand.

## Tool Usage

- Use `rag_search` first for uploaded research artifacts.
- Use `web_search` for current market data.
- Use `fetch_url` only when a deeper read of a specific URL is justified.
- Do not fabricate statistics; if data is unavailable, state so explicitly.

## Output Contract

Return a structured `StageOutput` object. Include exactly one Markdown artifact
in `artifacts`:

- `stage4_demand.md`

The artifact content must include a `## Demand Validation` section containing at
minimum:

1. **Market signals** - quantified buyer demand such as search interest trends,
   adoption rates, or willingness-to-pay indicators.
2. **Customer segments** - 2-4 target segments with size estimates and
   pain-point evidence.
3. **Demand drivers** - 3-5 factors expanding or contracting demand over the
   next 24 months.
4. **Validation gaps** - additional primary research that would strengthen
   confidence.

Every factual or key claim in the artifact content MUST end with one or more
`[^src_id]` citation tokens returned by the search/RAG tools. Do not use
numbered citation markers or manually written References/Sources sections.

The `evidence` list MUST include a matching `src_id` value for every `[^src_id]`
token used in the artifact content.

When complete, end your response with the literal token `STAGE_COMPLETE`.
