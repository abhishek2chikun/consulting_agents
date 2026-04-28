---
name: evidence-discipline
description: Use when making factual consulting claims, citing research, using web search outputs, distinguishing snippets from primary sources, attributing provider evidence, deciding whether to quote or paraphrase, or dropping material claims that cannot be sourced.
---

# Evidence Discipline

Make every material claim traceable to reliable evidence. Evidence discipline protects consulting outputs from unsupported assertions, fabricated citations, source laundering, and overconfident interpretation of weak sources.

---

## Overview

Consulting recommendations depend on trust. Trust requires that facts, numbers, quotes, and competitor-specific statements can be traced back to sources the reviewer can inspect.

The core principle: no URL or inspectable source means no citation by default. If a claim cannot be sourced, downgrade it to an assumption, remove it, or explicitly mark it as unsupported.

Evidence is not decoration. It is part of the reasoning chain from observation to implication to recommendation.

---

## When to Use

Use evidence discipline whenever the output includes:

- Market size, growth, share, pricing, financial, or operational claims.
- Competitor-specific statements.
- Customer behavior or adoption claims.
- Regulatory, legal, technical, or scientific claims.
- Quotes from executives, filings, websites, reviews, or interviews.
- Search results from web providers, RAG retrieval, or internal document search.
- Any claim that would change the recommendation if wrong.

Do not use citations to create false certainty. If evidence is weak, say it is weak.

---

## Core Framework

### Claim Classification

| Claim Type | Evidence Standard |
|---|---|
| Material factual claim | Cite a source with URL or source ID |
| Quantitative claim | Cite source and show calculation if transformed |
| Competitor-specific claim | Prefer primary source; never invent |
| Common business concept | Citation optional unless contested or central |
| Assumption | Label as assumption and explain basis |
| Inference | Cite underlying facts and state the reasoning |

### Source Hierarchy

| Source Type | Typical Confidence | Notes |
|---|---|---|
| Primary company source | High for company claims | Websites, filings, press releases, pricing pages |
| Government or regulator | High for official statistics and rules | Check date and definitions |
| Audited financial filing | High for reported financials | Watch fiscal year and segment definitions |
| Reputable industry report | Medium to high | Definitions may be paywalled or opaque |
| News article | Medium | Useful for events, not always for market sizing |
| Search snippet | Low | Use only to find the real source |
| Unsourced blog or AI summary | Low | Do not cite for material claims |

---

## Workflow

### Step 1: Identify Material Claims

Before finalizing an answer, scan for claims that are factual, quantitative, named, comparative, or recommendation-critical.

Material claim examples:

- "The market is growing at 12% annually."
- "Competitor A offers usage-based pricing."
- "Customers cite integration difficulty as the main adoption barrier."
- "The regulation requires annual reporting."

### Step 2: Attach Evidence as You Write

Cite claims at the sentence or bullet level. Do not save citations for a bibliography disconnected from claims.

Use a citation whenever the reader should be able to verify the statement independently.

### Step 3: Distinguish Source Types

Separate these categories:

- **Primary source**: the entity that created or owns the information.
- **Secondary source**: a third party reporting or interpreting primary information.
- **Search snippet**: provider-generated preview text that may be incomplete or stale.
- **RAG excerpt**: retrieved internal or uploaded content with a source ID.

A search snippet is not a source. Use it to navigate to the source, then cite the actual page or document.

### Step 4: Preserve Attribution

When evidence comes from a provider, preserve the provider attribution and source identifiers available in the tool output.

Capture:

- Provider name when available.
- Source title.
- URL or source ID.
- Publication date or document date.
- Accessed date if the source is web content likely to change.
- Relevant quote or data point.

### Step 5: Quote and Paraphrase Carefully

Use direct quotes only when the exact wording matters. Keep quotes short and exact.

When paraphrasing:

- Do not change scope, certainty, or causality.
- Do not combine two sources into one stronger claim unless both support it.
- Do not imply endorsement from a source that only reports an allegation or estimate.
- Keep numbers, dates, and definitions faithful to the source.

### Step 6: Drop Unsupported Claims

If evidence cannot be found, do one of three things:

- Remove the claim.
- Reframe it as an assumption with clear uncertainty.
- Replace it with a weaker claim that the evidence supports.

Never invent citations, URLs, report titles, source IDs, publication dates, or quoted language.

---

## Evidence Requirements

Each cited claim should make clear:

- What the source says.
- Which part of the recommendation the source supports.
- Whether the source is primary or secondary.
- Whether the claim is quoted, paraphrased, calculated, or inferred.
- The confidence level if evidence is mixed or indirect.

For calculations, cite the input sources and show the formula. A citation to one input does not validate the whole calculation.

For RAG evidence, cite the source ID or document identifier exactly as returned. If the retrieved passage lacks enough context, say so and avoid overstating it.

---

## Citation Discipline Checklist

Before submitting an output, check:

- Every material factual claim has a citation or is labeled as an assumption.
- Every competitor-specific claim has a primary source or a confidence caveat.
- Search snippets were not cited as if they were source documents.
- Quotes are exact and not stitched together.
- Paraphrases preserve the source meaning.
- Source IDs, URLs, titles, and providers are retained.
- Claims unsupported by evidence were dropped.
- Conflicting sources are acknowledged rather than hidden.

---

## Common Mistakes

| Mistake | Why It Fails | Better Practice |
|---|---|---|
| Citing a search result snippet | Snippets can be stale or generated | Open and cite the source page |
| Adding citations only at paragraph end | Unclear which claim is supported | Cite each material claim |
| Treating a vendor blog as neutral | Source has commercial bias | Label bias and triangulate |
| Inventing missing metadata | Fabricates evidence | Say metadata unavailable |
| Overstating a paraphrase | Changes source meaning | Preserve certainty and scope |
| Keeping uncited claims because they sound plausible | Creates hidden risk | Drop or label as assumption |
| Using one source for a broad conclusion | Overgeneralizes | Add triangulation or narrow the claim |

---

## Worked Example

Weak draft:

"Competitor A is the market leader and charges about $99 per month, while customers increasingly prefer AI-driven workflows."

Problems:

- "Market leader" needs a source and definition.
- Pricing needs a current primary pricing page or archived source.
- Customer preference needs survey, adoption, review, or interview evidence.
- The sentence combines three material claims without citations.

Disciplined rewrite:

"Competitor A lists its Pro plan at $99 per user per month on its pricing page [source: company pricing page, URL, accessed date]. Its leadership position is not established by the available sources; treat it instead as a named competitor with visible enterprise positioning. Evidence for customer preference toward AI-driven workflows was not found in the searched sources, so that claim should be removed or tested through customer research."

Decision:

- Keep the sourced pricing claim.
- Downgrade the leadership claim.
- Drop the customer preference claim until evidence exists.
