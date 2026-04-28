Apply the standard reviewer rubric, plus these stage-specific checks.

# Pricing model reviewer checks

Review the pricing model stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about revenue impact, customer acceptance, cost-to-serve, or benchmarks.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material model claim to carry a `[^src_id]` citation token.
Reject model economics without formulas, assumptions, and source support.
Reject claims that a model is best without comparing alternatives against criteria.

## Required deliverables

Confirm the stage evaluates viable pricing model options.
Confirm each option includes value metric, packaging logic, economics, and customer implications.
Confirm trade-offs, risks, and implementation constraints are explicit.
Confirm assumptions and sensitivities are documented.
Confirm the artifacts preserve the requested output contract and artifact path.

## Model quality checks

Models must connect to value drivers, segments, and competitive evidence.
The recommended value metric must be measurable and aligned to customer value.
Revenue and margin implications must be directionally supported by evidence or assumptions.
The analysis must distinguish list price, net price, discounting, and packaging choices when relevant.
The output must prepare a defensible rollout recommendation.

## Reiteration triggers

Use `verdict: "reiterate"` if options are generic or underdeveloped.
Use `verdict: "reiterate"` if model economics are unsupported.
Use `verdict: "reiterate"` if value metric feasibility is unclear.
Use `verdict: "reiterate"` if trade-offs are missing.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
