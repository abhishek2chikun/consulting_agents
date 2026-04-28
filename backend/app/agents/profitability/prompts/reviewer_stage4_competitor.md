Apply the standard reviewer rubric, plus these stage-specific checks.

# Competitor benchmark reviewer checks

Review the profitability competitor benchmark stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about competitor margins, cost structure, pricing, productivity, or benchmarks.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every competitor-specific benchmark claim to carry a `[^src_id]` citation token.
Reject benchmark figures without period, definition, and comparability caveats.
Reject inferred competitor economics unless assumptions and confidence are explicit.

## Required deliverables

Confirm the stage identifies relevant competitors or benchmark peers.
Confirm benchmark metrics are defined and normalized where possible.
Confirm differences in scale, business model, geography, and accounting treatment are considered.
Confirm evidence gaps and confidence levels are stated.
Confirm the artifacts preserve the requested output contract and artifact path.

## Benchmark quality checks

Peer set must be relevant to the client's economics and operating model.
Benchmark comparisons must not imply precision beyond the evidence.
The analysis must distinguish public facts from inferred operating implications.
Competitive gaps must connect to margin opportunity or strategic constraints.
The output must prepare the lever stage with realistic opportunity boundaries.

## Reiteration triggers

Use `verdict: "reiterate"` if competitor benchmark claims are uncited.
Use `verdict: "reiterate"` if peer comparability is not addressed.
Use `verdict: "reiterate"` if metrics use inconsistent definitions.
Use `verdict: "reiterate"` if inferred economics are presented as facts.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
