# Project 01 — GTM Container Auditor

Read the root `CLAUDE.md` and `ROADMAP.md` first. This file holds project-specific context only.

## Design thesis

**Code decides what code can decide. The model only makes judgment calls.**

Every rule in `src/rules.py` is decidable by inspecting the container graph — reference integrity, deprecated tag types, duplicate conversions, malformed selectors. None of it touches an LLM and none of it ever should. Adding an LLM call to `rules.py` is a regression, not an improvement.

`src/judge.py` handles only what has no deterministic answer:
- Is this custom HTML tag doing something risky?
- Does this dataLayer push or query-param decoration likely carry PII?
- Is this container's naming scheme internally coherent (beyond the mechanical checks)?
- What is the business impact ranking across findings?

The README must show this split explicitly. It is the point of the project.

## Source container

Built against a real container from a healthcare clinic (addiction/mental-health), anonymized. This matters for the audit itself — an ad-tech pixel firing unconditionally on a health site is a materially different finding than the same pixel on a retail site, and the LLM layer should be able to reason about that context.

- `data/private/original_container.json` — real export, **gitignored, never commit**
- `data/sample_container.json` — anonymized, committed, safe to publish
- Re-run anonymization: `python3 -m src.anonymize data/private/original_container.json data/sample_container.json`

`src/anonymize.py` fails closed — it refuses to write output if any identifying value survives its verification pass. Anonymization deliberately preserves ID *shape* (`G-`, `UA-`, `GTM-`) so format-based rules still fire on the public sample.

## Rule conventions

- One rule = one function, decorated with `@rule("GTMNNN")`, yielding `Finding`s.
- Rule IDs are permanent. Never renumber; retire by deleting the function and noting it in the README.
- Every `Finding` needs a `remediation` that a GTM admin can act on without asking a follow-up question.
- Severity reflects data/business impact, not effort to fix.
- `evidence` holds machine-readable specifics so `evals/` can assert on them.

## Verified findings on the sample container (2026-07-28)

21 deterministic findings, 16 rules. The two that matter most and that a manual audit usually misses:
- **GTM009** — `request_appointment_all` fires on the same triggers as `request_appointment_new` and `request_appointment_existing`, double-counting every appointment conversion.
- **GTM014** — the newsletter Element Visibility selector is a pasted class attribute with no `.` prefixes, so it matches nothing. The trigger is also orphaned (GTM001), so the bug was never noticed.

## Provider layer

Routes through OpenRouter (`_shared/llm.py`) so one key reaches open-weight and
frontier models alike. Model aliases resolve against the live `/models` endpoint
rather than being hardcoded — slugs carry date suffixes that change on release.

Routing is measured, not asserted. `JUDGE_MODEL_FAST` (default `deepseek`,
$0.14/$0.28 per M) handles naming coherence and impact ranking; `JUDGE_MODEL_DEEP`
(default `sonnet`, $2/$10) handles custom HTML risk and PII exposure. Whether that
split holds is an eval question, and the eval answers it with a table.

Schema violations are counted per model, not silently retried away — how often a
cheap model returns malformed structured output is the number that decides whether
it's usable for a task.

## Status

- [x] Steps 1–4: scaffold, anonymize, parse, deterministic rules
- [x] Step 5: LLM judgment layer (`src/judge.py`) — written, not yet run against the API
- [ ] Step 6: report renderer
- [ ] Steps 7–9: eval dataset, scoring, tuning
- [ ] Step 10: README, diagram, cost, push
