Apply the standard reviewer rubric, plus these stage-specific checks.

# Demand reviewer checks

Review the market-entry demand stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about buyer demand, adoption, willingness to switch, or purchase triggers.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material demand claim to carry a `[^src_id]` citation token.
Reject market-size figures without units, geography, period, and method.
Reject customer behavior claims that lack survey, usage, transaction, interview, or proxy evidence.

## Required deliverables

Confirm the stage quantifies or qualifies demand for the scoped market.
Confirm demand drivers, barriers, and adoption timing are addressed.
Confirm customer segments are tied to needs and evidence.
Confirm assumptions and sensitivities are explicit where estimates are uncertain.
Confirm the artifacts preserve the requested output contract and artifact path.

## Demand quality checks

Demand estimates must separate total market interest from reachable demand.
The analysis must explain why customers would buy or switch.
Segments must be decision-relevant, not merely demographic or generic.
Demand barriers must be weighed alongside drivers.
Implications must show whether demand supports entry timing and investment level.

## Reiteration triggers

Use `verdict: "reiterate"` if demand is asserted without evidence.
Use `verdict: "reiterate"` if estimates omit units, geography, or time period.
Use `verdict: "reiterate"` if segments do not connect to buyer behavior.
Use `verdict: "reiterate"` if assumptions are hidden.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
