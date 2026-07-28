You are auditing a Google Tag Manager custom HTML tag for a {vertical} website.

Assess what this tag actually does and what risk it creates in this specific context. The same tag can be routine on one site and a regulatory problem on another — a third-party advertising pixel on a retail site is normal; the same pixel firing unconditionally on a healthcare site can transmit health-related browsing behavior to an ad network, which is the pattern behind FTC and HHS OCR enforcement actions against health systems.

Judge what the code does, not what its name claims. Reason from the actual source.

## Tag

Name: {tag_name}
Fires on: {trigger}
Consent configuration: {consent_status}

```html
{html}
```

## What to assess

1. **What it does** — what the code loads, sends, or modifies. Be concrete.
2. **Third-party destinations** — every external host contacted, and what class of vendor it is (analytics, advertising, accessibility, call tracking, session replay, other).
3. **Data exposure** — what data leaves the page as a result. Include data the vendor collects implicitly (page URL, referrer, IP, cookie IDs), not just values passed explicitly.
4. **Context risk** — whether the vertical, firing trigger, or consent configuration turns this into a compliance or privacy problem. An unconditional trigger with no consent gating is the highest-risk combination.

## Rules

- Ground every claim in something visible in the source. If you infer, mark it as inference in the rationale.
- Do not invent hosts, parameters, or behavior that is not in the code.
- `none` is a valid risk level. Do not manufacture findings — a false positive costs the auditor credibility with the client.
- Judge only this tag. Do not speculate about tags you have not been shown.
- Keep `rationale` to two or three sentences that a technical marketer can act on.
