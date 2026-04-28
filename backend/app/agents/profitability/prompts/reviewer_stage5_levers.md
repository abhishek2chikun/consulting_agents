Apply the standard reviewer rubric, plus these stage-specific checks.

# Profit levers reviewer checks

Review the profitability lever stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about revenue upside, cost savings, margin impact, feasibility, or timing.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material lever claim to carry a `[^src_id]` citation token.
Reject impact estimates without baseline, formula, assumptions, and sensitivity.
Reject implementation feasibility claims that ignore risks or operating constraints.

## Required deliverables

Confirm the stage identifies prioritized profit improvement levers.
Confirm each lever includes value, effort, timing, risk, owner or capability need, and KPI.
Confirm sequencing and dependencies are explicit.
Confirm assumptions, sensitivities, and decision gates are documented.
Confirm the artifacts preserve the requested output contract and artifact path.

## Lever quality checks

Levers must connect to revenue, cost, margin, and benchmark findings.
Impact ranges must avoid false precision and double counting.
Prioritization must balance value, feasibility, risk, and time to impact.
The plan must distinguish quick wins from structural improvements.
The recommendation must be specific enough for synthesis to use.

## Reiteration triggers

Use `verdict: "reiterate"` if lever impact is unsupported.
Use `verdict: "reiterate"` if priorities lack criteria.
Use `verdict: "reiterate"` if dependencies or risks are missing.
Use `verdict: "reiterate"` if levers are generic cost-cutting ideas.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
