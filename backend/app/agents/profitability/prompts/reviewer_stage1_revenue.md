Apply the standard reviewer rubric, plus these stage-specific checks.

# Revenue reviewer checks

Review the profitability revenue stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about revenue mix, volume, price, retention, growth, or customer behavior.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material revenue claim to carry a `[^src_id]` citation token.
Reject revenue calculations without formulas, units, period, and source support.
Reject confident driver conclusions when the evidence only supports correlation or hypothesis.

## Required deliverables

Confirm the stage describes the revenue baseline and major drivers.
Confirm price, volume, mix, retention, and acquisition effects are considered where relevant.
Confirm the artifacts identify revenue leakage or upside hypotheses.
Confirm assumptions, data gaps, and sensitivity are explicit.
Confirm the artifacts preserve the requested output contract and artifact path.

## Revenue quality checks

Revenue drivers must be separated rather than blended into generic growth commentary.
Calculations must use consistent periods, currencies, and units.
Customer or channel claims must be backed by evidence.
The analysis must distinguish historical performance from future improvement potential.
Implications must connect to later cost, margin, and lever analysis.

## Reiteration triggers

Use `verdict: "reiterate"` if revenue figures are uncited.
Use `verdict: "reiterate"` if calculations cannot be traced.
Use `verdict: "reiterate"` if driver decomposition is missing.
Use `verdict: "reiterate"` if assumptions are presented as facts.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
