Apply the standard reviewer rubric, plus these stage-specific checks.

# Cost reviewer checks

Review the profitability cost stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about fixed costs, variable costs, labor, procurement, operations, or overhead.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material cost claim to carry a `[^src_id]` citation token.
Reject savings claims without baseline, method, and source support.
Reject benchmark comparisons that do not normalize for scale, scope, or operating model.

## Required deliverables

Confirm the stage describes the cost structure and major cost pools.
Confirm fixed versus variable behavior is addressed where relevant.
Confirm cost drivers, constraints, and controllability are explicit.
Confirm assumptions, data gaps, and sensitivity are stated.
Confirm the artifacts preserve the requested output contract and artifact path.

## Cost quality checks

Cost categories must be meaningful for management action.
Savings opportunities must distinguish addressable cost from total spend.
The analysis must avoid double counting cost pools or benefits.
Operational constraints must be considered before recommending cuts.
Implications must connect to margin and lever analysis.

## Reiteration triggers

Use `verdict: "reiterate"` if cost figures are uncited.
Use `verdict: "reiterate"` if fixed and variable costs are confused.
Use `verdict: "reiterate"` if savings estimates are unsupported.
Use `verdict: "reiterate"` if controllability is not addressed.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
