"""Report renderer and audit entry point.

Merges deterministic and LLM findings into a client-ready markdown report plus a
machine-readable findings.json.

Two things this file deliberately does that most audit tools don't:

  * **Every finding is labelled with its source.** A reader can see which findings
    a rule proved and which a model judged. That distinction is the difference
    between "this tag has no trigger" and "this tag looks risky" — a client
    deserves to know which one they're reading, and it is the whole thesis of
    this project made visible in the deliverable.

  * **Limitations are a section, not an omission.** A container export is static
    config. It cannot tell you whether a tag actually fires, what the dataLayer
    contains at runtime, or what a vendor does with the data. Saying so protects
    the client from over-reading the report and is why project 05 exists.

Runs without an API key via --no-llm, producing the deterministic report for free.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _shared.llm import Ledger, LLMError, load_dotenv  # noqa: E402

from .parse import Container, load  # noqa: E402
from .rules import REGISTRY, Finding, SEVERITY_ORDER, run_all  # noqa: E402

SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "info": "Info",
}
SOURCE_LABEL = {
    "deterministic": "rule",
    "llm": "model judgment",
}
CRITERION_LABEL = {
    "regulatory_exposure": "Regulatory exposure",
    "decision_corrupting_data": "Decision-corrupting data",
    "silent_measurement_loss": "Silent measurement loss",
    "maintenance_burden": "Maintenance burden",
}


def _order(findings: list[Finding], impact: dict[int, dict]) -> list[tuple[int, Finding]]:
    """Impact rank first where the judge supplied one, severity otherwise.

    Findings the judge never ranked sort after ranked ones rather than being
    dropped — an unranked finding is still a finding.
    """
    def key(pair: tuple[int, Finding]) -> tuple:
        idx, f = pair
        meta = impact.get(idx)
        return (
            0 if meta else 1,
            meta["rank"] if meta else 0,
            SEVERITY_ORDER.get(f.severity, 9),
            f.rule_id,
        )

    return sorted(enumerate(findings), key=key)


def _counts(findings: list[Finding]) -> dict[str, int]:
    counts = {s: 0 for s in SEVERITY_LABEL}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _evidence_lines(evidence: dict) -> list[str]:
    out = []
    for key, value in evidence.items():
        if value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                rendered = "; ".join(
                    ", ".join(f"{k}: {v}" for k, v in item.items()) for item in value[:6]
                )
            else:
                rendered = ", ".join(f"`{v}`" for v in value[:12])
        else:
            rendered = str(value)
        out.append(f"  - {label}: {rendered}")
    return out


def build_report(
    container: Container,
    findings: list[Finding],
    impact: dict[int, dict],
    ledger: Ledger | None,
    vertical: str,
    llm_enabled: bool,
) -> str:
    counts = _counts(findings)
    ordered = _order(findings, impact)
    det = [f for f in findings if f.source == "deterministic"]
    llm = [f for f in findings if f.source == "llm"]

    L: list[str] = []
    add = L.append

    add(f"# GTM Container Audit — {container.name}")
    add("")
    add(f"**Container** `{container.public_id}` &nbsp;·&nbsp; "
        f"**Audited** {date.today().isoformat()} &nbsp;·&nbsp; "
        f"**Site profile** {vertical}")
    add("")
    summary = container.summary()
    add(" · ".join(
        f"{n} {noun if n == 1 else noun + 's'}"
        for n, noun in [
            (summary["tags"], "tag"),
            (summary["triggers"], "trigger"),
            (summary["user_variables"], "user variable"),
            (summary["builtin_variables"], "built-in variable"),
        ]
    ))
    add("")

    # -- executive summary ----------------------------------------------------
    add("## Executive summary")
    add("")
    add(f"**{len(findings)} findings.** "
        + " · ".join(f"{counts[s]} {SEVERITY_LABEL[s].lower()}"
                     for s in SEVERITY_LABEL if counts.get(s)))
    add("")

    ranked = [(i, f) for i, f in ordered if i in impact][:5]
    if ranked:
        add("Ranked by business impact rather than by severity — a high-severity "
            "finding on unused config matters less than a medium-severity one that "
            "silently corrupts reported numbers.")
        add("")
        for i, f in ranked:
            meta = impact[i]
            criterion = CRITERION_LABEL.get(meta["criterion"], meta["criterion"])
            add(f"{meta['rank']}. **{f.entity_name}** — {criterion}  ")
            add(f"   {meta['business_consequence']}")
            add("")
    else:
        add("Impact ranking was not run. Findings below are ordered by severity.")
        add("")

    # -- findings -------------------------------------------------------------
    add("## Findings")
    add("")
    for severity in SEVERITY_LABEL:
        group = [(i, f) for i, f in ordered if f.severity == severity]
        if not group:
            continue
        add(f"### {SEVERITY_LABEL[severity]} ({len(group)})")
        add("")
        for i, f in group:
            source = SOURCE_LABEL.get(f.source, f.source)
            add(f"#### `{f.rule_id}` {f.entity_name}")
            add("")
            add(f"*{f.entity_type} · {f.category.replace('_', ' ')} · determined by {source}*")
            add("")
            add(f.message)
            add("")
            if meta := impact.get(i):
                add(f"**Business impact (rank {meta['rank']}).** {meta['business_consequence']}")
                add("")
            if f.remediation:
                add(f"**Fix.** {f.remediation}")
                add("")
            if lines := _evidence_lines(f.evidence):
                add("<details><summary>Evidence</summary>")
                add("")
                add("\n".join(lines))
                add("")
                add("</details>")
                add("")

    # -- methodology ----------------------------------------------------------
    add("## How this audit was produced")
    add("")
    add(f"**{len(det)} findings from deterministic rules** — {len(REGISTRY)} rules "
        "evaluated against the container's reference graph. These are proven from "
        "the export: a tag either has a trigger or it doesn't. No model was involved.")
    add("")
    if llm_enabled:
        add(f"**{len(llm)} findings from model judgment** — applied only to questions "
            "with no deterministic answer: third-party risk in the site's context, "
            "PII exposure through generic data-moving code, naming coherence, and "
            "business-impact ranking. Every such finding is labelled above.")
        add("")
        if ledger and ledger.calls:
            s = ledger.summary()
            add("| Model | Calls | Tokens | Cost |")
            add("|---|---:|---:|---:|")
            for model, stats in sorted(s["by_model"].items()):
                add(f"| `{model}` | {stats['calls']} | {stats['tokens']:,} | "
                    f"${stats['cost_usd']:.4f} |")
            add(f"| **Total** | **{s['calls']}** | **{s['total_tokens']:,}** | "
                f"**${s['total_cost_usd']:.4f}** |")
            add("")
            add(f"Schema violation rate: {s['schema_violation_rate']:.1%} "
                "(malformed structured output, retried).")
            add("")
    else:
        add("**Model judgment was not run** for this report (`--no-llm`). Third-party "
            "risk, PII exposure, and impact ranking are therefore not covered.")
        add("")

    # -- limitations ----------------------------------------------------------
    add("## Limitations")
    add("")
    add("This audit reads a static container export. It establishes what the "
        "container is configured to do, not what happens in a browser. Specifically, "
        "it cannot determine:")
    add("")
    add("- Whether a tag actually fires, or fires more than once per page")
    add("- What the dataLayer contains at runtime, or what values reach each tag")
    add("- Whether a consent platform blocks tags before they load, independently of "
        "the container's own consent settings")
    add("- What a third-party vendor does with data after it leaves the page")
    add("- Anything in a container version other than the one exported")
    add("")
    add("Confirming those requires live testing against the running site.")
    add("")

    return "\n".join(L).rstrip() + "\n"


def write_outputs(report: str, findings: list[Finding], impact: dict[int, dict],
                  ledger: Ledger | None, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "audit_report.md"
    json_path = out_dir / "findings.json"

    md_path.write_text(report)
    json_path.write_text(json.dumps({
        "generated": date.today().isoformat(),
        "findings": [
            {**f.to_dict(), "impact": impact.get(i)}
            for i, f in enumerate(findings)
        ],
        "usage": ledger.summary() if ledger and ledger.calls else None,
    }, indent=2) + "\n")
    return md_path, json_path


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Audit a GTM container export.")
    ap.add_argument("container", nargs="?", default="data/sample_container.json")
    ap.add_argument("--vertical", default="general business",
                    help="Site profile. Changes how third-party risk is judged.")
    ap.add_argument("--no-llm", action="store_true",
                    help="Deterministic rules only. No API key needed, no cost.")
    ap.add_argument("--out", default="reports", help="Output directory.")
    args = ap.parse_args()

    load_dotenv()
    container = load(args.container)
    findings = run_all(container)
    impact: dict[int, dict] = {}
    ledger: Ledger | None = None

    if not args.no_llm:
        from .judge import run as run_judge
        try:
            llm_findings, impact, ledger = run_judge(container, findings, args.vertical)
            findings = findings + llm_findings
        except LLMError as exc:
            print(f"\nModel judgment unavailable: {exc}\n"
                  "Rendering deterministic findings only.\n", file=sys.stderr)

    report = build_report(container, findings, impact, ledger,
                          args.vertical, llm_enabled=not args.no_llm)
    md_path, json_path = write_outputs(report, findings, impact, ledger, Path(args.out))

    counts = _counts(findings)
    print(f"{len(findings)} findings — "
          + ", ".join(f"{counts[s]} {s}" for s in SEVERITY_LABEL if counts.get(s)))
    print(f"  {md_path}")
    print(f"  {json_path}")
    if ledger and ledger.calls:
        print(f"  cost: ${ledger.total_cost_usd:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
