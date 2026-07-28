# Roadmap

Six projects, ordered as a deliberate difficulty ramp. Each one adds exactly one new AI capability on top of the last, and each is anchored in analytics work so it doubles as domain proof.

| # | Project | AI capability demonstrated | Est. build | Status |
|---|---------|---------------------------|-----------|--------|
| 01 | GTM Container Auditor | Structured output + determinism split | 1–2 sessions | ⬜ Not started |
| 02 | NL→SQL Agent (GA4 BigQuery) | Schema-grounded tool use + guardrails | 2–3 sessions | ⬜ Not started |
| 03 | Analytics Knowledge RAG | Retrieval, chunking, citation, retrieval eval | 2–3 sessions | ⬜ Not started |
| 04 | Experiment Readout Agent | Multi-step reasoning + calibrated uncertainty | 2 sessions | ⬜ Not started |
| 05 | Tagging Audit Orchestrator | Multi-agent orchestration + parallel fan-out | 3–4 sessions | ⬜ Not started |
| 06 | Eval Harness | LLM-as-judge + regression testing across 01–05 | 2 sessions | ⬜ Not started |

A "session" is 2–3 focused hours. Update Status to 🟡 In progress / ✅ Done with the GitHub link as each completes.

**Why this order:** it mirrors how AI engineering competency is actually assessed — single-call reliability, then tool use, then retrieval, then agentic reasoning, then orchestration, then measurement. Building them out of order means rebuilding shared infrastructure.

---

## 01 — GTM Container Auditor

**Elevator line:** Point it at a GTM container export and get a structured audit report — misconfigured tags, missing triggers, orphaned variables, naming-convention violations, PII risk in dataLayer pushes.

**AI capability:** Schema-enforced structured output, and the *determinism split* — code checks what code can check, the model only makes judgment calls. This is the single most important idea in production AI work and most portfolios get it backwards.

**Input:** GTM container export JSON (the standard `Export Container` file). Use a synthetic/anonymized container in `data/`.
**Output:** `audit_report.md` + `findings.json` with severity-ranked findings.

**Build steps:**
1. `mkdir 01-gtm-container-auditor` and scaffold the standard folder structure from `CLAUDE.md`.
2. Export a GTM container you control, anonymize IDs, save to `data/sample_container.json`. Write a short note in `data/README.md` on what was anonymized.
3. Write the **parser** (`src/parse.py`) — load the export, build tag/trigger/variable objects, resolve references between them. No LLM yet.
4. Write the **deterministic rules** (`src/rules.py`) — orphaned tags, triggers referencing missing variables, tags with no trigger, duplicate tag names, hardcoded IDs, naming-convention regex. Each rule returns `{rule_id, severity, entity, message}`. Aim for 10–12 rules. This is pure Python; zero AI.
5. Add the **LLM layer** (`src/judge.py`) — only for things rules can't decide: is this custom HTML tag risky? does this dataLayer push likely contain PII? is this naming scheme internally consistent? Enforce output with a JSON schema via tool use. Use the cheap model for classification, expensive only for the custom-HTML risk read.
6. Write the **reporter** (`src/report.py`) — merge deterministic + LLM findings, rank by severity, render markdown.
7. Build `evals/dataset.jsonl` — ≥15 containers or container fragments with known planted defects and the expected findings. Include 3 clean cases to test for false positives.
8. Write `evals/run_eval.py` — score precision and recall on finding detection. Record in `evals/results.md`.
9. Tune. Log which failures were rule gaps vs. model errors — that analysis is portfolio gold, put it in the README.
10. README + architecture diagram + cost per run. Push.

**Eval metric:** Precision and recall on planted defects, reported separately for deterministic rules vs. LLM findings. False-positive rate on clean containers.

**Reviewer takeaway:** "This person knows not to use an LLM where a `for` loop works."

---

## 02 — NL→SQL Agent (GA4 BigQuery Export)

**Elevator line:** Ask "what was mobile conversion rate by traffic source last week" and get correct SQL against the GA4 BigQuery export schema, executed, with results.

**AI capability:** Schema-grounded tool use, query validation before execution, retry-on-error loops, and cost guardrails. The GA4 export schema (nested `event_params`, `user_properties`) is genuinely hard — that's the point.

**Input:** Natural-language question. **Output:** SQL + result table + a plain-English answer.

**Build steps:**
1. Scaffold. Set up a BigQuery project with the **public GA4 sample dataset** (`bigquery-public-data.ga4_obfuscated_sample_ecommerce`) so this runs for anyone cloning it — no client data, no credentials problem.
2. Write `src/schema.py` — programmatically pull table schema + the distinct `event_name` values + distinct `event_params.key` values. This grounding step is what stops hallucinated column names.
3. Write the system prompt with the GA4 unnest patterns baked in as few-shot examples. Keep it in `src/prompts/` as a separate file, versioned — not inline in code.
4. Add SQL generation with structured output: `{sql, tables_referenced, assumptions, confidence}`.
5. Add **validation before execution** — dry-run the query in BigQuery, capture bytes-scanned, reject anything over a configurable limit. Feed dry-run errors back to the model for one retry, max two.
6. Execute and summarize results in plain English. The summarizer must not see the raw question alone — pass it the SQL too, so it describes what was actually computed.
7. `evals/dataset.jsonl` — ≥20 questions with gold SQL or gold answer values. Include 3 deliberately ambiguous questions where correct behavior is to ask a clarifying question, not to guess.
8. `evals/run_eval.py` — score on execution match (does generated SQL return the same values as gold SQL), not string match. Report separately: valid-SQL rate, execution-match rate, appropriate-clarification rate.
9. README, diagram, cost per query (include BigQuery bytes scanned, not just tokens). Push.

**Eval metric:** Execution-accuracy on gold set. Report the failure taxonomy — schema errors vs. logic errors vs. ambiguity.

**Reviewer takeaway:** "This person can put an LLM in front of a warehouse without it inventing columns or burning $400 on a full-table scan."

---

## 03 — Analytics Knowledge RAG

**Elevator line:** Ask questions of a tracking-plan corpus — measurement specs, GA4 docs, naming conventions, past audit reports — and get cited answers.

**AI capability:** Retrieval design. Chunking strategy, hybrid search, citation enforcement, and — the part most people skip — evaluating *retrieval* separately from *generation*.

**Input:** A corpus of markdown/PDF measurement documentation. **Output:** Answer with inline citations to source chunk.

**Build steps:**
1. Scaffold. Assemble the corpus in `data/corpus/` — write 8–12 realistic synthetic tracking plans, event dictionaries, and naming-convention docs. Volume matters less than variety of structure (tables, nested specs, prose).
2. Write `src/chunk.py`. Try two strategies and keep both switchable: naive fixed-size, and structure-aware (split on headings, keep tables intact). You will show the eval difference between them in the README — that comparison is the portfolio value.
3. Embed and index. Start with a local vector store (Chroma or LanceDB) so it runs offline. Add BM25 keyword search alongside — analytics queries are full of exact identifiers (`purchase`, `ga_session_id`) that embeddings handle poorly.
4. Implement hybrid retrieval with reciprocal rank fusion. Add a reranking pass.
5. Generation with **enforced citation** — the model must return `{answer, citations: [chunk_id]}` and you programmatically verify every cited chunk_id exists and every claim maps to one. Reject and retry if not.
6. Build **two** eval sets: `evals/retrieval.jsonl` (query → which chunk_ids must be retrieved; score recall@k) and `evals/generation.jsonl` (query → gold answer; score correctness + citation validity).
7. Run the eval across both chunking strategies and both retrieval modes (vector-only vs. hybrid). Table the four results in `evals/results.md`.
8. README with the comparison table front and center, diagram, cost. Push.

**Eval metric:** recall@5 for retrieval; answer correctness + citation-validity rate for generation. Reported per configuration.

**Reviewer takeaway:** "This person evaluated retrieval and generation separately." Almost nobody does.

---

## 04 — Experiment Readout Agent

**Elevator line:** Feed it A/B test results (Statsig/GA4 export) and it produces a stakeholder-ready readout — with the statistical honesty to say "not enough data" instead of declaring a winner.

**AI capability:** Multi-step reasoning over quantitative data, and **calibrated uncertainty** — refusing to overclaim. Directly reusable on the Woodmark work.

**Input:** Experiment results CSV/JSON (variant, users, conversions, revenue, by segment). **Output:** Structured readout — result, confidence, segment findings, recommendation, caveats.

**Build steps:**
1. Scaffold. Generate synthetic experiment datasets in `data/` spanning: clear winner, clear loser, underpowered/inconclusive, Simpson's paradox across device, and a sample-ratio-mismatch case.
2. Write `src/stats.py` — significance testing, confidence intervals, power calculation, SRM chi-square check. **All statistics are computed in Python. The model never does math.** Enforce this hard; it's the whole design thesis.
3. Write `src/agent.py` — the model receives computed stats as structured input and produces interpretation: what happened, for whom, what to do. Structured output with an explicit `verdict` enum: `ship | do_not_ship | inconclusive | invalid_test`.
4. Add the **guardrail chain**: SRM failure forces `invalid_test` regardless of what the model says. Power below threshold forces `inconclusive`. These are code-level overrides on model output — demonstrate that you constrain the model rather than trusting it.
5. Add segment analysis with a multiple-comparisons correction, and have the agent flag when a segment finding is likely noise.
6. Render to a stakeholder markdown/DOCX readout.
7. `evals/dataset.jsonl` — ≥15 experiments with gold verdicts. Weight heavily toward inconclusive and invalid cases; that's where models fail.
8. Score verdict accuracy, and separately score **overclaim rate** (how often it declares a winner when it shouldn't). Overclaim rate is the headline metric.
9. README, diagram, cost. Push.

**Eval metric:** Verdict accuracy; overclaim rate on underpowered/invalid tests (target: 0%).

**Reviewer takeaway:** "This person built an AI system that knows when to shut up."

---

## 05 — Tagging Audit Orchestrator

**Elevator line:** Given a domain, it crawls key pages, captures network requests and dataLayer state, runs parallel specialist agents (GA4, GTM, consent, PII), and produces a full tagging audit.

**AI capability:** Multi-agent orchestration — task decomposition, parallel fan-out, result synthesis, failure isolation, and cost control at scale. This is the flagship.

**Input:** Domain + page list. **Output:** Multi-section audit report with per-page findings.

**Build steps:**
1. Scaffold. Decide the orchestration layer up front and document why: n8n (visual, shows the automation skill, easier for a client to inherit) vs. Claude Agent SDK (more control, better for the code-portfolio read). **Recommendation: build the core in the Agent SDK, then wrap it in an n8n workflow for scheduling.** You get both stories.
2. Build the **collector** first, no AI — Playwright script that loads a page, captures all network requests, snapshots `dataLayer`, records consent-state changes. Save to structured JSON per page. Get this rock solid before adding agents.
3. Define the **specialist agents**, each with a narrow scope and its own output schema:
   - GA4 agent — event coverage vs. expected, parameter completeness, duplicate hits
   - GTM agent — container health, tags firing that shouldn't
   - Consent agent — tags firing pre-consent, consent-mode signals
   - PII agent — emails/phones/IDs in query params, dataLayer, or event payloads
4. Build the **orchestrator** — fan out pages × agents in parallel, with per-agent timeout and failure isolation (one agent dying must not kill the run). Cap concurrency. Log token spend per agent.
5. Build the **synthesizer** — dedupe findings across pages, promote site-wide patterns above per-page noise, rank by severity. Deduplication happens in code against a finding key, not by asking a model to dedupe.
6. Add cost controls: per-run token budget, cheap model for extraction agents, expensive only for the synthesizer. Document the routing.
7. `evals/` — 3–5 known sites (or locally hosted fixture pages with deliberately planted tagging defects). Score finding recall and false-positive rate.
8. Wrap in n8n for scheduled runs; export the workflow JSON into the repo.
9. README, architecture diagram (this one needs a real one), cost per site. Push.

**Eval metric:** Finding recall against planted defects; false-positive rate; cost and wall-clock per site.

**Reviewer takeaway:** "This is a product, not a demo." This is the one that gets consulting inquiries.

---

## 06 — Eval Harness

**Elevator line:** A single harness that runs regression evals across projects 01–05, tracks scores over time, and catches quality regressions from prompt or model changes.

**AI capability:** LLM-as-judge with judge validation, regression testing, and score tracking across model versions. This is the project that says "I've operated AI systems, not just built them."

**Build steps:**
1. Scaffold. Define a common eval interface every project conforms to — a `run_eval.py` exposing `evaluate(dataset) -> {metric: score}`. Retrofit 01–05 to match; expect small refactors.
2. Build the runner — discovers projects, executes their evals, writes timestamped results to `results/history.jsonl`.
3. Add an **LLM-as-judge** for the open-ended outputs (03 answers, 04 readouts, 05 reports). Judge prompt returns a rubric score with reasoning, structured.
4. **Validate the judge.** Hand-label 30 outputs, measure judge agreement with your labels (Cohen's kappa). Report it. An unvalidated judge is a fabricated metric — saying this out loud in the README is a differentiator.
5. Add regression detection — flag any metric dropping more than a threshold vs. the last run.
6. Add a **model comparison mode** — run the same eval across Opus / Sonnet / Haiku and table accuracy vs. cost vs. latency. This directly justifies the routing decisions claimed in projects 01–05.
7. Build a simple dashboard — Looker Studio off a Sheets export, or a static HTML report. Looker Studio is the better play; it's your tool and it makes the whole portfolio feel operational.
8. Schedule it in n8n to run weekly and push notifications on regressions.
9. README, diagram. Push.

**Eval metric:** This one *is* the metric. Report judge-human agreement and time-to-detect on an injected regression.

**Reviewer takeaway:** "This person measures their AI systems and validates the measurement."

---

## Cross-cutting: the writeup

After 03 is done, write `_docs/portfolio-overview.md` — a single page linking all projects with the one-line capability each demonstrates. That page is what goes in the resume link and the LinkedIn featured section. Don't wait until all six are finished; ship it at the halfway point and update it.
