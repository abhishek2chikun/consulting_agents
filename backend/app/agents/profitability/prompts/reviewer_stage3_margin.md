Apply the standard reviewer rubric, plus these stage-specific checks.

# Margin reviewer checks

Review the profitability margin stage as a strict partner gate.
Do not replace the standard reviewer criteria; apply these checks in addition.

## Evidence discipline

Reject unsupported claims about gross margin, contribution margin, EBITDA, mix, or profitability drivers.
Reject fabricated citations, invented source IDs, and citations that do not support the sentence.
Require every material margin claim to carry a `[^src_id]` citation token.
Reject margin calculations without numerator, denominator, period, and source support.
Reject conclusions that attribute margin movement without evidence.

## Required deliverables

Confirm the stage synthesizes revenue and cost findings into margin drivers.
Confirm margin metrics are defined consistently.
Confirm product, customer, channel, or geography mix effects are addressed where relevant.
Confirm assumptions, data gaps, and sensitivity are explicit.
Confirm the artifacts preserve the requested output contract and artifact path.

## Margin quality checks

Margin bridge logic must be traceable from inputs to conclusion.
The analysis must separate structural margin issues from temporary effects.
Mix effects must not be asserted without supporting data.
Margin improvement implications must avoid double counting revenue and cost levers.
The output must prepare a clear basis for competitor benchmarking and lever prioritization.

## Reiteration triggers

Use `verdict: "reiterate"` if margin math is unclear or uncited.
Use `verdict: "reiterate"` if metric definitions are inconsistent.
Use `verdict: "reiterate"` if drivers are asserted without evidence.
Use `verdict: "reiterate"` if revenue and cost findings are not integrated.
Use `verdict: "reiterate"` if required stage deliverables are missing.

## Output requirements

Return the same structured reviewer output schema as the standard rubric.
Do not invent new fields, markdown, or explanatory prose outside the JSON object.
When reiterating, make `gaps` concrete and actionable.
When targeting agents, name only the deficient agent slugs available in the run.
The rationale should explain why the stage can or cannot advance.
