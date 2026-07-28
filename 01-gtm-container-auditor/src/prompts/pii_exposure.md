You are auditing a Google Tag Manager container for a {vertical} website to find where personally identifiable information, or protected health information, could leak into analytics or advertising systems.

The leaks that matter in practice are rarely explicit. They usually come from mechanisms that move data around generically: query parameters copied across domains, URLs captured wholesale into analytics, form-field values read from the DOM, or user identifiers appended to links pointing at third parties.

## Data flows found in this container

{flows}

## What to assess

1. **Identifiers at risk** — what kinds of PII or PHI could travel through these mechanisms. Consider what a real user journey on this kind of site would place into a URL, form, or dataLayer.
2. **Destinations of concern** — which flows send data somewhere it should not go. Pay particular attention to cross-domain movement, anything reaching an advertising or marketing vendor, and any endpoint whose name or host implies regulated data handling.
3. **Mechanism** — the specific code path that creates the exposure, quoted from what you were given.

## Rules

- Ground every claim in the flows above. Do not assume tags or fields you have not been shown.
- Distinguish confirmed exposure (the data provably moves) from potential exposure (the mechanism would carry it if the value is present). Say which you mean.
- Passing marketing attribution parameters between first-party domains is normal and is not by itself a finding. Passing them into a regulated form endpoint, or passing user-identifying values to an advertising vendor, is.
- `none` is a valid risk level. Report clean when it is clean.
