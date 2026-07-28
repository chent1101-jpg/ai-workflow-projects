# AI Workflow Projects

## What this repo is

A portfolio of self-contained projects that prove I can design, build, and **evaluate** AI workflows — not just call an LLM API. Each subfolder is one project, independently runnable, with its own README, and demonstrating a distinct AI capability anchored in web analytics / marketing data.

Audience is dual: hiring managers screening for analytics + AI roles, and prospective consulting clients. Every project must survive a stranger cloning it and running it in under 10 minutes.

Owner: Tim Chen. See `~/.claude/CLAUDE.md` for background and stack.

## How Claude should work in this repo

- **One project at a time.** Do not scaffold multiple projects in a single session. Finish, run, and document one before starting the next.
- **Build in the stated step order** from `ROADMAP.md`. When I say "start project 02," read that project's spec in `ROADMAP.md`, restate the step list, and begin at step 1.
- **Give me the next concrete action, always.** End every response with the specific command, file, or edit that comes next.
- **Working code over explanation.** Skip AI-101 preamble. I know GTM, SQL, and the analytics stack — explain only the AI-specific tradeoff (chunking strategy, tool-schema design, eval metric choice, model routing, cost).
- **Nothing ships without an eval.** A project with no `evals/` directory and no measured score is not done. This is the single thing that separates this portfolio from every other "I built a chatbot" repo — treat it as non-negotiable, not an extra.
- **Verify before claiming done.** Run the thing. Paste real output. If it fails, say so with the error.
- **Do not use Agent/subagents or workflows unless I ask for it.**

## Repo layout

```
AI Workflow Projects/
├── CLAUDE.md              # this file — conventions + rules
├── ROADMAP.md             # project slate, specs, and build steps
├── _shared/               # code reused across projects (LLM client, logging, cost tracking)
├── _docs/                 # cross-project writeups, architecture notes, screenshots
├── 01-gtm-container-auditor/
├── 02-nl-to-sql-ga4/
├── 03-analytics-knowledge-rag/
├── 04-experiment-readout-agent/
├── 05-tagging-audit-orchestrator/
└── 06-eval-harness/
```

Numbered prefixes are build order, not priority. Numbering is fixed once created — do not renumber.

## Required structure for every project folder

```
NN-project-name/
├── README.md              # see contract below
├── CLAUDE.md              # project-specific context for Claude (optional but preferred)
├── .env.example           # every key referenced, no real values
├── requirements.txt       # or package.json — pinned versions
├── src/                   # implementation
├── evals/
│   ├── dataset.jsonl      # test cases with expected outputs
│   ├── run_eval.py        # scores the system against dataset
│   └── results.md         # latest scores, dated, with failure analysis
├── data/                  # sample/synthetic inputs — never real client data
└── docs/
    └── architecture.md    # diagram + why this design over alternatives
```

## README contract

Every project README must contain, in this order:

1. **One-sentence description** — what it does, for whom.
2. **The AI concept demonstrated** — named explicitly (e.g. "schema-grounded tool use with deterministic guardrails"). This is what a reviewer is scanning for.
3. **Architecture diagram** — Mermaid, inline in the markdown.
4. **Quickstart** — clone → env → install → run, copy-pasteable, verified working.
5. **Eval results** — table: metric, score, date, sample size. Link to `evals/results.md`.
6. **Design decisions & tradeoffs** — 3–5 bullets, each stating the alternative rejected and why.
7. **Known limitations** — honest. Reviewers trust this more than a perfect claim.
8. **Cost per run** — measured tokens × current pricing.

## Conventions

**Models.** Default to Claude. Current IDs: `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`. Route deliberately — cheap model for extraction/classification, expensive for reasoning/judgment — and document the routing decision in the README. Before writing any Anthropic API code, load the `claude-api` skill; do not write model IDs, pricing, or params from memory.

**Secrets.** Never commit keys. `.env` is gitignored; `.env.example` lists every variable with a placeholder. No real client data, no real container IDs, no real property IDs in committed files — synthesize or anonymize.

**Language.** Python for data/LLM pipelines. TypeScript/React only when there's a UI. n8n for scheduled or event-driven orchestration, with the workflow JSON exported to the repo.

**Cost tracking.** Every LLM call logs tokens in and out. `_shared/` holds the wrapper that does this. A project that can't answer "what does one run cost?" is incomplete.

**Structured output.** Prefer tool-use / JSON-schema-enforced output over parsing free text. If a project parses model prose with regex, that's a design flaw to fix, not a shortcut to keep.

**Determinism split.** Anything that can be checked with code (counts, schema validity, thresholds) is checked with code. The LLM handles only judgment. Every project README should be able to point at where that line is drawn.

## Definition of done (per project)

- [ ] Runs end-to-end from a clean clone using only `README.md`
- [ ] `evals/results.md` has a dated score against ≥15 test cases
- [ ] Architecture diagram renders
- [ ] Measured cost per run documented
- [ ] No secrets, no real client data
- [ ] Pushed to GitHub, public, with a description and topics set
- [ ] Root `ROADMAP.md` status updated to ✅ with the repo link

## Git

Root folder is one repo (`ai-workflow-projects`) containing all projects — a reviewer clicks once, not six times. Commit per meaningful step, not per session. Branch for anything spanning more than one session.
