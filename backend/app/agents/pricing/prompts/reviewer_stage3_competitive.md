Apply the standard reviewer rubric, plus these stage-specific checks.

# Competitive pricing reviewer checks

Review the pricing competitive stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about competitor price points, packaging, discounting, or positioning.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every competitor-specific pricing claim to carry a `[^src_id]` citation token.
Reject inferred prices unless assumptions and confidence are explicit.
Reject benchmarking that mixes incomparable products without caveats.

## Required deliverables

Confirm the stage identifies relevant pricing competitors and alternatives.
Confirm competitor pricing, packaging, value metric, and positioning are compared where available.
Confirm the artifacts distinguish observed facts from interpretation.
Confirm evidence gaps and unknowns are clearly flagged.
Confirm the artifacts preserve the requested output contract and artifact path.

## Competitive quality checks

Competitor set must match the target segment and use case.
Price comparisons must normalize for unit, tier, bundle, contract term, and feature scope.
The analysis must identify price corridors and white-space opportunities only when supported.
Competitive implications must not default to underpricing without evidence.
The output must show how competitor evidence constrains model and rollout choices.

## Reiteration triggers

Use `verdict: "reiterate"` if competitor prices are uncited.
Use `verdict: "reiterate"` if comparisons ignore bundle or tier differences.
Use `verdict: "reiterate"` if unknown pricing is fabricated.
Use `verdict: "reiterate"` if implications are generic.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
