Apply the standard reviewer rubric, plus these stage-specific checks.

# Rollout reviewer checks

Review the pricing rollout stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about adoption, churn risk, sales readiness, experimentation, or revenue lift.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material rollout claim to carry a `[^src_id]` citation token.
Reject financial uplift estimates without assumptions, baseline, and sensitivity.
Reject implementation claims that ignore operational constraints found in prior stages.

## Required deliverables

Confirm the stage presents a pricing recommendation and rollout plan.
Confirm the plan includes sequencing, experiments, migration approach, governance, and KPIs.
Confirm risks, customer communications, and sales enablement needs are addressed.
Confirm assumptions, dependencies, and decision gates are explicit.
Confirm the artifacts preserve the requested output contract and artifact path.

## Rollout quality checks

The plan must connect to value, segments, competitive evidence, and selected model.
Experiments must define target segment, hypothesis, metric, and decision rule.
Migration guidance must handle existing customers where relevant.
KPIs must include commercial outcomes and customer response indicators.
The recommendation must be specific enough for synthesis to use.

## Reiteration triggers

Use `verdict: "reiterate"` if rollout sequencing is vague.
Use `verdict: "reiterate"` if experiments lack metrics or decision rules.
Use `verdict: "reiterate"` if revenue impact is unsupported.
Use `verdict: "reiterate"` if customer or sales risks are ignored.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
