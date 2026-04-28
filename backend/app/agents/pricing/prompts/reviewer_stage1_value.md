Apply the standard reviewer rubric, plus these stage-specific checks.

# Value reviewer checks

Review the pricing value stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about customer value, willingness to pay, ROI, pain severity, or benefits.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material value claim to carry a `[^src_id]` citation token.
Reject value claims based only on internal opinion unless clearly labeled as assumptions.
Reject quantified ROI or savings without formula, inputs, and source support.

## Required deliverables

Confirm the stage defines the value drivers that pricing should capture.
Confirm customer pains, outcomes, and economic benefits are explicit.
Confirm willingness-to-pay evidence or defensible proxies are included.
Confirm assumptions and confidence levels are stated where evidence is incomplete.
Confirm the artifacts preserve the requested output contract and artifact path.

## Value quality checks

Value drivers must be linked to customer decision criteria.
Benefits must distinguish hard financial impact from qualitative value.
Willingness-to-pay proxies must be explained and not overstated.
The analysis must identify which value pools are monetizable.
Implications must show how value should influence later segmentation and model choices.

## Reiteration triggers

Use `verdict: "reiterate"` if value is asserted without evidence.
Use `verdict: "reiterate"` if ROI math lacks inputs or citations.
Use `verdict: "reiterate"` if willingness-to-pay is invented or generic.
Use `verdict: "reiterate"` if monetizable value is unclear.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
