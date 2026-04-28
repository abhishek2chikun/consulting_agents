---
name: unit-economics
description: Use when analyzing revenue per unit, variable costs, contribution margin, gross margin, CAC, LTV, payback, churn, retention, break-even, cohort profitability, sensitivity ranges, or whether a growth model creates profitable customer-level economics.
---

# Unit Economics

Analyze whether each customer, order, subscription, location, transaction, or account creates profitable value after the costs required to serve and acquire it. Unit economics turns growth claims into a testable profit engine.

---

## Overview

A business can grow revenue while destroying value if the unit model is weak. Unit economics isolates the repeatable unit of value creation and tests whether revenue, variable cost, retention, and acquisition dynamics support profitable scaling.

The core principle: define the unit first, then trace revenue and cost behavior per unit before discussing scale benefits.

Good unit economics are explicit about time period, customer cohort, margin definition, and what costs are included or excluded.

---

## When to Use

Use unit economics when evaluating:

- Pricing strategy or monetization changes.
- Profitability improvement opportunities.
- Marketplace, SaaS, subscription, usage-based, or transaction models.
- Customer acquisition efficiency.
- Retention, churn, and lifetime value.
- Break-even volume or payback period.
- Growth plans that require marketing, sales, subsidy, or service investment.
- Diligence on whether reported growth can become profitable.

Do not use blended averages alone when cohorts, segments, channels, or geographies behave differently.

---

## Core Framework

### Define the Unit

Common units include:

- Customer or account.
- Subscriber or seat.
- Order or transaction.
- Delivery, trip, booking, or job.
- Store, clinic, branch, or location.
- Device, asset, or installed base unit.

The unit should match the economic decision. For pricing, the unit may be a seat or usage event. For expansion strategy, it may be a customer cohort. For operations, it may be an order or delivery.

### Core Metrics

| Metric | Formula | Use |
|---|---|---|
| Revenue per unit | Total unit revenue / units | Monetization strength |
| Variable cost per unit | Costs that vary with the unit / units | Cost-to-serve |
| Contribution margin | Revenue per unit - variable cost per unit | Profit before fixed costs |
| Contribution margin % | Contribution margin / revenue | Scalability of the model |
| Gross margin | Revenue - cost of goods sold | Accounting margin view |
| CAC | Sales and marketing acquisition cost / new customers | Cost to acquire demand |
| LTV | Contribution margin over retained customer life | Customer value |
| Payback period | CAC / monthly contribution margin | Time to recover acquisition spend |

Contribution margin and gross margin are not the same. Contribution margin includes all variable costs needed to serve the unit, even if accounting gross margin excludes some of them.

---

## Workflow

### Step 1: Choose the Economic Unit

State the unit, period, and segment:

"Unit economics are measured per [customer/order/subscription] for [segment/channel/geography] over [period]."

Avoid mixing customer-level and order-level economics in the same calculation unless you explicitly bridge between them.

### Step 2: Calculate Revenue per Unit

Revenue may include:

- Subscription fees.
- Usage charges.
- Product sales.
- Transaction fees or take rate.
- Add-on, upsell, or cross-sell revenue.
- Refunds, credits, discounts, or churn adjustments.

Use net revenue when refunds, discounts, incentives, payment failures, or platform fees materially affect economics.

### Step 3: Identify Variable Costs

Variable costs may include:

- Product cost or cost of goods sold.
- Payment processing fees.
- Fulfillment, delivery, support, onboarding, and success costs.
- Cloud infrastructure or usage-based software costs.
- Contractor labor tied to units.
- Returns, warranties, fraud, bad debt, and chargebacks.

Do not allocate fixed overhead into unit economics unless the purpose is fully loaded profitability. Keep contribution margin and fully loaded margin separate.

### Step 4: Compute Contribution Margin

Use this structure:

- Revenue per unit.
- Less variable cost per unit.
- Equals contribution margin per unit.
- Divide by revenue for contribution margin percentage.

If contribution margin is negative, scaling the unit increases losses unless price, mix, retention, or variable costs change.

### Step 5: Add CAC, Retention, and LTV

For customer economics, connect acquisition and retention:

- CAC by channel or cohort.
- Gross retention and net revenue retention.
- Logo churn and revenue churn.
- Average customer lifetime or retention curve.
- Expansion revenue and contraction revenue.
- LTV based on contribution margin, not just revenue.

Simple LTV approximation:

LTV = annual contribution margin per customer / annual churn rate.

Use cohort curves when churn is not stable or when early-life churn differs from mature retention.

### Step 6: Analyze Payback and Break-even

Payback period indicates how long acquisition spend is at risk.

Break-even can be calculated as:

- Fixed costs / contribution margin per unit.
- CAC / monthly contribution margin per customer.
- Required orders per location / contribution margin per order.

State the break-even volume and compare it to actual capacity or demand.

### Step 7: Sensitize Key Drivers

Test low/base/high cases for:

- Price or ARPU.
- Order frequency or usage.
- Variable cost per unit.
- CAC.
- Conversion rate.
- Churn or retention.
- Expansion revenue.

Identify which driver changes the recommendation.

---

## Evidence Requirements

Every unit economics analysis should cite or document:

- Source of revenue, unit count, and cohort data.
- Definition of variable costs included.
- CAC calculation period and included spend categories.
- Retention or churn measurement method.
- Whether LTV uses gross margin or contribution margin.
- Treatment of discounts, refunds, incentives, and one-time onboarding fees.
- Segment, geography, channel, and time period.

If data is unavailable, label assumptions clearly and show sensitivity. Do not convert missing cost data into zero cost.

---

## Common Mistakes

| Mistake | Why It Fails | Better Practice |
|---|---|---|
| Using blended averages | Hides bad cohorts or channels | Segment by cohort, channel, or customer type |
| Calculating LTV on revenue | Overstates value | Use contribution margin |
| Ignoring churn timing | Misstates lifetime | Use retention curves when available |
| Allocating fixed costs as variable | Confuses scale economics | Separate contribution and fully loaded margin |
| Double counting CAC | Penalizes acquisition twice | Define included sales and marketing costs |
| Excluding support or onboarding | Understates cost-to-serve | Include variable service costs |
| Treating payback as profitability | Payback ignores lifetime risk | Pair with LTV and retention |
| Using mature retention for new cohorts | Overstates growth economics | Use cohort-specific retention |

---

## Worked Example

Question: Are paid search customers for a B2B SaaS product economically attractive?

Definitions:

- Unit: new paid-search customer.
- Period: monthly subscription cohort.
- Segment: small business customers.
- Revenue basis: net monthly recurring revenue.

Base calculation:

- ARPU: $120 per month.
- Variable cloud, support, and payment cost: $30 per month.
- Contribution margin: $90 per month, or 75%.
- CAC from paid search: $900 per new customer.
- Monthly gross churn: 4%.

Outputs:

- Payback period: $900 / $90 = 10 months.
- Approximate LTV: ($90 x 12) / 48% annual churn = $2,250.
- LTV:CAC: 2.5x.

Interpretation:

- The channel is viable but not exceptional.
- If churn rises to 6% monthly, LTV falls materially and LTV:CAC may drop below the target threshold.
- The recommendation should focus on retention improvement or CAC reduction before scaling paid search aggressively.
