---
name: financial-modeling
description: Build financial models for business cases including ROI, NPV, IRR, scenario analysis, and total cost of ownership. Use when developing investment recommendations, comparing strategic options, quantifying the value of initiatives, building business cases, performing cost-benefit analysis, or valuing a business unit for strategic decisions. Covers standard financial analysis workflows (ROI, business case, cash flow projections, break-even, DCF) and advanced techniques (EVA, MIRR, real options, Monte Carlo thinking, discount rate selection).
---

# Financial Modeling

Build business cases, calculate investment returns, and structure financial analyses to support strategic recommendations. Applies the modeling techniques used in consulting engagements.

---

## Behavioral Principles

1. **Document every assumption.** State the source, basis, and confidence level for each assumption. Undocumented assumptions are the #1 cause of flawed business cases.
2. **Be conservative by default.** Use realistic, not optimistic, assumptions. Stretch goals are not baseline projections. If a client pushes for aggressive numbers, flag the risk explicitly.
3. **Sensitivity over precision.** A precise but wrong number is worse than an approximate range. Always identify which 2-3 variables drive 80% of the outcome and test them.
4. **Show alternatives.** Never present a single option. Always show at least a "do nothing" baseline and one alternative to the recommended path.
5. **Separate facts from forecasts.** Clearly distinguish historical data from projected values. Label assumptions as "verified," "estimated," or "placeholder."
6. **Make it auditable.** Structure models so a third party can trace any output back to its source assumptions in under 5 minutes.
7. **The number supports the decision.** The business case exists to support a decision, not to generate a number. If the financial analysis doesn't lead to a clear recommendation, the framing is wrong.

---

## Analysis Type Selection

| Analysis Type | Use Case | Key Outputs |
|---|---|---|
| ROI Analysis | Quick investment assessment | Return %, payback period |
| Business Case | Comprehensive investment case | NPV, IRR, payback |
| DCF Valuation | Company or business unit valuation | Enterprise value, equity value |
| Scenario Analysis | Risk assessment | Best/base/worst case, probability-weighted NPV |
| Break-even Analysis | Volume or revenue threshold | Break-even point, margin of safety |
| TCO Comparison | Comparing competing solutions | Annualized cost, cost per user |
| EVA | Cross-unit performance comparison | Value creation vs. capital cost |

---

## ROI Analysis

For quick investment assessment, structure the analysis as:

**Investment Summary**: Initial investment, ongoing investment per year, project life.

**Benefits Projection**: For each benefit category, project Year 1 through end of project life with totals.

**Return Metrics**:
- Simple ROI (%) against a benchmark
- Payback period against acceptable threshold
- NPV (must be positive)
- IRR (must exceed cost of capital)

**Sensitivity**: Identify the 2-3 variables that drive the outcome and show NPV impact at +/- 10% variation.

---

## Business Case Development

For comprehensive investment cases, structure as:

**Executive Summary**: 2-3 sentences on the investment and recommendation.

**Problem Statement**: What problem does this investment solve?

**Financial Summary**: Total investment, NPV (base case), IRR, payback period, ROI.

**Investment Details**: Cost categories (capital, implementation, ongoing opex) projected across the analysis period.

**Benefit Projections**: Revenue growth, cost reduction, risk mitigation, and other quantifiable benefits projected across the analysis period.

**Cash Flow Analysis**: Annual cash flows with discount factors and present values. Show the NPV calculation explicitly.

**Assumptions**: List every assumption. Include the discount rate and analysis period. Label each assumption as verified, estimated, or placeholder.

**Sensitivity Analysis**: Show NPV, IRR, and assessment under upside, base, and downside scenarios.

**Risks and Mitigations**: Each risk with quantified impact, likelihood (H/M/L), and specific mitigation.

**Recommendation**: Go/No-Go with rationale tied directly to the analysis.

---

## DCF Valuation

For business or company valuation:

**Revenue Projections**: Revenue, growth rate, EBITDA, and margin for current year through Year 5.

**Terminal Value**: Method (Gordon Growth or Exit Multiple), terminal growth rate, exit multiple, and resulting terminal value.

**WACC Calculation**: Debt and equity weights, costs, and resulting WACC.

**Valuation Sensitivity**: Show enterprise value in a matrix of WACC (+/- 1%) vs. terminal growth rate (+/- 1%).

---

## Scenario Analysis

For risk assessment:

**Scenario Definitions**: Upside, base, and downside with description and probability weighting.

**Scenario Comparison**: Revenue, costs, NPV, IRR, and payback under each scenario.

**Probability-Weighted NPV**: Each scenario's NPV times its probability, summed to expected NPV.

**Break-even Analysis**: Break-even revenue, break-even volume, and margin of safety.

---

## Economic Value Added (EVA)

**Formula**: EVA = NOPAT - (WACC x Capital Employed)

Where:
- NOPAT = Net Operating Profit After Tax
- WACC = Weighted Average Cost of Capital
- Capital Employed = Total Assets - Current Liabilities

Interpretation:
- Positive EVA: Creates value for shareholders
- Negative EVA: Destroys value
- Compare EVA across business units to identify value creators vs. destroyers

When to use EVA:
- Comparing performance across divisions of different sizes
- Evaluating whether growth is actually creating value
- Setting performance targets that account for capital cost
- Assessing acquisition targets (is the target generating returns above its cost of capital?)

---

## Discount Rate Selection

### Factors

| Factor | Consideration | Impact on Rate |
|---|---|---|
| Cost of capital | Company's WACC | Baseline |
| Risk level | Project risk vs. company average | +/- adjustment |
| Industry | Industry average returns | Benchmark |
| Inflation | Expected inflation rate | Include |
| Market conditions | Current interest rates | Adjust |
| Technology risk | AI/technology implementation uncertainty | + adjustment |

### Typical Ranges by Risk Level

| Risk Level | Discount Rate Range | Examples |
|---|---|---|
| Low risk | 5-8% | Core operations, efficiency improvements |
| Medium risk | 8-12% | Growth initiatives |
| High risk | 12-20% | New market entry |
| Very high risk | 20%+ | New ventures, R&D |
| Platform/AI | 15-25% | Digital transformation, AI investments |

### Guidance

- When in doubt, use a higher discount rate. Better to reject a good project than to accept a bad one.
- If a project looks attractive only at a low discount rate, flag it as sensitive to cost-of-capital assumptions.
- Always show NPV at multiple discount rates (e.g., WACC, WACC+2%, WACC+5%).

---

## Total Cost of Ownership (TCO)

### Cost Categories

**Direct Costs** (by year): Acquisition, implementation, operation, maintenance, upgrade/replacement.

**Indirect Costs**: Training, productivity loss during implementation, support overhead, compliance/certification.

**Hidden Costs** (often missed):
- Data migration and integration
- Dual-running during transition
- Vendor lock-in switching costs
- Technical debt accumulation
- Opportunity cost of internal resources

**TCO Summary**: Total TCO, annualized TCO, cost per user/year, and comparison vs. alternatives.

### When to Use TCO vs. Simple ROI

- **Use TCO** when comparing competing solutions (build vs. buy, vendor A vs. vendor B)
- **Use ROI** when evaluating a single investment against a do-nothing baseline
- **Use both** when the decision involves both "should we do it?" and "how should we do it?"

---

## Advanced Valuation Concepts

### Modified IRR (MIRR)

Standard IRR assumes reinvestment at the IRR rate, which is often unrealistic. MIRR corrects this by specifying:
- **Financing rate**: Cost to fund the project (typically WACC)
- **Reinvestment rate**: Rate earned on interim cash flows (typically cost of capital or a conservative market rate)

Use MIRR when the project has non-standard cash flows (multiple sign changes) or when IRR produces multiple solutions.

### Real-Options Valuation

Traditional NPV undervalues projects with embedded flexibility. Real-options thinking adds value for:
- **Option to expand**: Invest small now, scale up if successful
- **Option to abandon**: Cut losses if early results are poor
- **Option to defer**: Wait for better information before committing
- **Option to switch**: Change inputs, outputs, or technology mid-project

Apply real-options thinking when:
- Investments are staged (especially R&D, pilot programs)
- High-uncertainty environments where flexibility has tangible value
- Platform investments where future use cases are uncertain
- Traditional NPV is negative but "close" and flexibility may tip the balance

### Monte Carlo Simulation

For major investments, point-estimate scenarios (best/base/worst) understate the range of outcomes:
- Assign probability distributions to key assumptions (not just three points)
- Run thousands of iterations to produce a probability distribution of outcomes
- Report: probability of positive NPV, expected NPV, 5th/95th percentile range
- Use to identify which assumptions contribute most to outcome variance

---

## AI and Technology Investment Modeling

Technology and AI investments have cost and benefit structures that differ from traditional capital projects.

### Cost Patterns
- **Cloud infrastructure**: Operating expense, scales with usage (not fixed capital)
- **Data costs**: Acquisition, cleaning, labeling, storage... often underestimated
- **AI/ML talent**: Scarce and expensive; model as ongoing cost, not one-time
- **Technical debt**: Accumulates if not managed; include remediation budget

### Benefit Patterns
- **Automation savings**: High confidence, easy to quantify
- **Prediction/decision quality**: Medium confidence, model as error-rate reduction
- **Personalization uplift**: Measurable via A/B testing, but adoption curve matters
- **Platform/network effects**: Hard to model precisely; use scenario analysis

### Modeling Guidance
- Separate "proven" benefits (automation) from "speculative" benefits (network effects)
- Use higher discount rates for speculative benefits
- Model adoption curves. AI benefits rarely arrive at full scale in Year 1
- Include a "technology pivot" scenario where the chosen approach needs to change

---

## Forecasting Techniques

- **Driver-based forecasting**: Build from operational drivers (units, prices, headcount) rather than top-down growth rates. More transparent and auditable.
- **Predictive analytics**: Use ML models for demand forecasting when sufficient historical data exists.
- **Scenario generation**: Consider additional scenarios based on historical variance, not just optimistic/pessimistic.
- **Anomaly detection**: Flag unusual patterns in assumption inputs that may signal errors.

---

## Model Standards

### Structure
- Single source of truth for assumptions (one assumptions section)
- Clear inputs vs. outputs separation
- Scenario switches that update the entire model from one control
- Sensitivity tables linked to key outputs

### Quality Controls
- Audit trails for changes to assumptions
- Cell-level comments explaining non-obvious formulas
- Error checks that flag circular references, broken links, or out-of-range values

### Presentation
- Executive summary that fits on one page
- Drill-down from summary metrics to supporting detail
- Sensitivity tables alongside headline numbers, not buried in an appendix

---

## Key Principles

- The "number" is never the point. The business case supports a decision.
- Finance and strategy must work together. Numbers without story lack impact.
- Sensitivity analysis is more important than precise projections.
- Always stress-test the business case with realistic downside scenarios.
- Be prepared to explain every assumption.
- If you can't explain it simply, you don't understand it well enough.
