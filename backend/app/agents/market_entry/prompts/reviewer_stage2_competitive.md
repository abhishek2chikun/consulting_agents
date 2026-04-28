Apply the standard reviewer rubric, plus these stage-specific checks.

# Competitive reviewer checks

Review the market-entry competitive stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about named competitors, pricing, market share, channels, or positioning.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every competitor-specific claim to carry a `[^src_id]` citation token.
Treat search snippets and summaries as leads, not final evidence, unless supported by artifacts.
Reject analysis that fills evidence gaps with plausible-sounding competitor details.

## Required deliverables

Confirm the stage identifies relevant direct and adjacent competitors.
Confirm competitor comparisons include dimensions that matter for entry strategy.
Confirm the artifacts distinguish facts from interpretation.
Confirm the artifacts include evidence confidence or caveats where data is weak.
Confirm the artifacts preserve the requested output contract and artifact path.

## Competitive quality checks

The competitor roster must be relevant to the defined market boundary.
Comparisons must avoid generic SWOT language unless backed by observed evidence.
Competitor strengths and weaknesses must connect to buyer choice or entry barriers.
Pricing, product, channel, and partnership claims must be sourced.
Implications must identify where the entrant can differentiate or where competition is intense.

## Reiteration triggers

Use `verdict: "reiterate"` if named competitor claims are uncited.
Use `verdict: "reiterate"` if the roster misses obvious relevant competitors.
Use `verdict: "reiterate"` if claims are copied across competitors without evidence.
Use `verdict: "reiterate"` if the competitive implications are generic.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
