You are ranking audit findings for a {vertical} website by business impact, to decide what the client fixes first.

Severity was already assigned mechanically from the class of defect. That is not the same as impact. A high-severity finding on a tag nobody uses matters less than a medium-severity finding that silently corrupts the numbers an executive reports. Your job is to re-rank by consequence.

## Findings

{findings}

## Ranking criteria, in order

1. **Regulatory or legal exposure** — anything creating liability under health-privacy, consumer-privacy, or consent law. Ranks first regardless of mechanical severity.
2. **Decision-corrupting data** — findings that make reported numbers wrong in a direction nobody will notice. Inflated conversions are worse than missing conversions, because missing data prompts investigation and inflated data prompts confident bad decisions.
3. **Silent measurement loss** — tracking that has never worked. Bad, but the absence is usually visible.
4. **Maintenance burden** — dead configuration, hardcoded values, naming drift. Real cost, no urgency.

## What to produce

For each finding, its `id` copied exactly from the input, its rank, the criterion that placed it, and one sentence naming the concrete business consequence — what breaks, who notices, what decision it distorts.

## Rules

- Return exactly one row per input finding, reusing the input `id` verbatim. Never invent, combine, or renumber an id — if two findings share a root cause, rank them adjacently and say so in the consequence, but keep them as separate rows with their own ids.
- Rank every finding you are given. Do not drop or merge any.
- Assign the criterion that matches the consequence you describe. If your sentence argues a finding is low-risk, do not file it under regulatory exposure.
- Write the consequence for the person who signs off on the fix, not for the engineer who applies it. "Every appointment conversion is counted twice, so reported cost-per-acquisition is understated by roughly half" beats "duplicate event tags."
- Do not invent findings. Rank only what you were given.
