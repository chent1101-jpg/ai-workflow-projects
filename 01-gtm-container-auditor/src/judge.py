"""LLM judgment layer.

This module handles ONLY what `rules.py` cannot decide. If a check has a right
answer that code can compute, it belongs in `rules.py` — adding it here is a
regression. The four questions here have no deterministic answer:

  1. Is this custom HTML tag doing something risky in this site's context?
  2. Could PII or PHI leak through the container's generic data-moving code?
  3. Is the naming scheme internally coherent beyond mechanical checks?
  4. Which findings actually matter to the business, versus which merely score high?

Model routing is deliberate and measured, not asserted: cheap model for the two
tasks that are close to classification, expensive model for the two that require
reasoning about consequence. `evals/` scores whether that split holds up.
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from _shared.llm import LLMClient, Ledger, LLMError, _progress, load_dotenv  # noqa: E402

from .parse import Container, Tag  # noqa: E402
from .rules import Finding  # noqa: E402

PROMPTS = Path(__file__).parent / "prompts"

RISK_LEVELS = ["none", "low", "medium", "high", "critical"]
# LLM risk level -> Finding severity. "none" produces no Finding at all.
SEVERITY_FROM_RISK = {
    "critical": "critical", "high": "high",
    "medium": "medium", "low": "low",
}

HTML_RISK_SCHEMA = {
    "type": "object",
    "required": ["risk_level", "category", "what_it_does", "third_party_hosts",
                 "data_exposure", "context_risk", "rationale", "recommendation"],
    "additionalProperties": False,
    "properties": {
        "risk_level": {"type": "string", "enum": RISK_LEVELS},
        "category": {"type": "string", "enum": [
            "advertising", "analytics", "accessibility", "call_tracking",
            "session_replay", "functionality", "other"]},
        "what_it_does": {"type": "string"},
        "third_party_hosts": {"type": "array", "items": {"type": "string"}},
        "data_exposure": {"type": "array", "items": {"type": "string"}},
        "context_risk": {"type": "string"},
        "rationale": {"type": "string"},
        "recommendation": {"type": "string"},
    },
}

PII_SCHEMA = {
    "type": "object",
    "required": ["risk_level", "identifiers_at_risk", "destinations_of_concern",
                 "rationale", "recommendation"],
    "additionalProperties": False,
    "properties": {
        "risk_level": {"type": "string", "enum": RISK_LEVELS},
        "identifiers_at_risk": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["identifier", "status", "mechanism"],
                "additionalProperties": False,
                "properties": {
                    "identifier": {"type": "string"},
                    "status": {"type": "string", "enum": ["confirmed", "potential"]},
                    "mechanism": {"type": "string"},
                },
            },
        },
        "destinations_of_concern": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "recommendation": {"type": "string"},
    },
}

NAMING_SCHEMA = {
    "type": "object",
    "required": ["coherence_score", "observed_conventions", "violations",
                 "recommended_standard", "rationale"],
    "additionalProperties": False,
    "properties": {
        "coherence_score": {"type": "integer"},
        "observed_conventions": {"type": "array", "items": {"type": "string"}},
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "issue", "suggested"],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "issue": {"type": "string"},
                    "suggested": {"type": "string"},
                },
            },
        },
        "recommended_standard": {"type": "string"},
        "rationale": {"type": "string"},
    },
}

RANKING_SCHEMA = {
    "type": "object",
    "required": ["ranked"],
    "additionalProperties": False,
    "properties": {
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "rank", "criterion", "business_consequence"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "integer"},
                    "rank": {"type": "integer"},
                    "criterion": {"type": "string", "enum": [
                        "regulatory_exposure", "decision_corrupting_data",
                        "silent_measurement_loss", "maintenance_burden"]},
                    "business_consequence": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM = (
    "You are a senior web analytics engineer auditing a Google Tag Manager "
    "container. You are precise, you ground every claim in the evidence you were "
    "given, and you do not manufacture findings to appear thorough. Reporting "
    "clean when something is clean is a correct answer."
)


def _prompt(name: str, **kwargs) -> str:
    return (PROMPTS / f"{name}.md").read_text().format(**kwargs)


class Judge:
    """Wraps the four judgment calls. One Ledger per audit run tracks cost."""

    def __init__(self, vertical: str, ledger: Ledger | None = None):
        self.vertical = vertical
        self.ledger = ledger if ledger is not None else Ledger()
        fast = os.environ.get("JUDGE_MODEL_FAST", "deepseek")
        deep = os.environ.get("JUDGE_MODEL_DEEP", "sonnet")
        self.fast = LLMClient(fast, ledger=self.ledger)
        self.deep = LLMClient(deep, ledger=self.ledger)

    # -- 1. custom HTML risk --------------------------------------------------

    def html_risk(self, container: Container, tag: Tag) -> Finding | None:
        result = self.deep.complete_json(
            system=SYSTEM,
            user=_prompt(
                "html_risk",
                vertical=self.vertical,
                tag_name=tag.name,
                trigger=", ".join(container.trigger_name(t) for t in tag.firing_trigger_ids),
                consent_status=tag.consent_status,
                html=tag.html[:12_000],
            ),
            schema=HTML_RISK_SCHEMA,
            task="html_risk",
            schema_name="html_risk",
        )
        if result["risk_level"] == "none":
            return None
        return Finding(
            "LLM001", SEVERITY_FROM_RISK[result["risk_level"]], "third_party_risk",
            "tag", tag.name,
            f"{result['what_it_does']} {result['context_risk']}".strip(),
            result["recommendation"],
            {
                "category": result["category"],
                "third_party_hosts": result["third_party_hosts"],
                "data_exposure": result["data_exposure"],
                "rationale": result["rationale"],
            },
            source="llm",
        )

    # -- 2. PII / PHI exposure ------------------------------------------------

    def pii_exposure(self, container: Container) -> Finding | None:
        flows = self._data_flows(container)
        if not flows:
            return None
        result = self.deep.complete_json(
            system=SYSTEM,
            user=_prompt("pii_exposure", vertical=self.vertical,
                         flows=json.dumps(flows, indent=2)[:12_000]),
            schema=PII_SCHEMA,
            task="pii_exposure",
            schema_name="pii_exposure",
        )
        if result["risk_level"] == "none":
            return None
        return Finding(
            "LLM002", SEVERITY_FROM_RISK[result["risk_level"]], "privacy",
            "container", container.name,
            result["rationale"], result["recommendation"],
            {
                "identifiers_at_risk": result["identifiers_at_risk"],
                "destinations_of_concern": result["destinations_of_concern"],
            },
            source="llm",
        )

    @staticmethod
    def _data_flows(container: Container) -> list[dict]:
        """Collect the container's generic data-moving mechanisms, deterministically.

        The model judges risk; it does not go looking for the code itself.
        """
        flows: list[dict] = []
        for tag in container.tags:
            if tag.type == "html" and tag.html:
                lowered = tag.html.lower()
                if any(k in lowered for k in
                       ("location.search", "urlsearchparams", ".href", "document.cookie",
                        "queryparams", "form", "datalayer", "localstorage")):
                    flows.append({
                        "kind": "custom_html",
                        "name": tag.name,
                        "fires_on": [container.trigger_name(t) for t in tag.firing_trigger_ids],
                        "source": tag.html[:4_000],
                    })
        for var in container.variables:
            if domains := var.params.get("autoLinkDomains"):
                flows.append({
                    "kind": "cross_domain_linker",
                    "name": var.name,
                    "linked_domains": domains,
                })
        return flows

    # -- 3. naming coherence --------------------------------------------------

    def naming_coherence(self, container: Container) -> Finding | None:
        result = self.fast.complete_json(
            system=SYSTEM,
            user=_prompt(
                "naming_coherence",
                tag_names="\n".join(f"  - {t.name}" for t in container.tags),
                trigger_names="\n".join(f"  - {t.name}" for t in container.triggers),
                variable_names="\n".join(f"  - {v.name}" for v in container.variables) or "  (none)",
            ),
            schema=NAMING_SCHEMA,
            task="naming_coherence",
            schema_name="naming_coherence",
        )
        if result["coherence_score"] >= 4:
            return None
        return Finding(
            "LLM003", "low", "hygiene", "container", container.name,
            f"Naming coherence scored {result['coherence_score']}/5. {result['rationale']}",
            result["recommended_standard"],
            {
                "observed_conventions": result["observed_conventions"],
                "violations": result["violations"],
            },
            source="llm",
        )

    # -- 4. business impact ranking -------------------------------------------

    def rank_by_impact(self, findings: list[Finding]) -> dict[int, dict]:
        """Return {finding_index: {rank, criterion, business_consequence}}.

        Keyed on an integer index we assign, not on rule_id — the model will
        happily invent a composite id like "LLM001_LLM002" when it decides two
        findings share a root cause, and any join on model-authored identifiers
        silently drops those rows.
        """
        if not findings:
            return {}
        payload = [
            {"id": i, "rule_id": f.rule_id, "entity_name": f.entity_name,
             "severity": f.severity, "message": f.message}
            for i, f in enumerate(findings)
        ]
        result = self.fast.complete_json(
            system=SYSTEM,
            user=_prompt("impact_ranking", vertical=self.vertical,
                         findings=json.dumps(payload, indent=2)[:20_000]),
            schema=RANKING_SCHEMA,
            task="impact_ranking",
            schema_name="impact_ranking",
        )

        valid = range(len(findings))
        ranked = {
            r["id"]: {
                "rank": r["rank"],
                "criterion": r["criterion"],
                "business_consequence": r["business_consequence"],
            }
            for r in result["ranked"] if r["id"] in valid
        }
        if dropped := len(result["ranked"]) - len(ranked):
            _progress(f"  WARNING: ranking returned {dropped} row(s) with unknown ids")
        if missing := set(valid) - set(ranked):
            _progress(f"  WARNING: {len(missing)} finding(s) were not ranked")
        return ranked


def run(container: Container, deterministic: list[Finding], vertical: str,
        ledger: Ledger | None = None, max_workers: int = 6
        ) -> tuple[list[Finding], dict, Ledger]:
    """Run the judgment layer. Returns (llm_findings, impact_map, ledger).

    The per-tag risk calls, the PII pass, and the naming pass are independent, so
    they run concurrently. Only the impact ranking is sequential — it needs every
    other finding as input. Sequentially this took ~9 minutes on a 19-tag
    container, which is too slow for a per-client tool.
    """
    judge = Judge(vertical, ledger)

    jobs: list[tuple[str, Any]] = [
        (f"html_risk:{tag.name}", lambda t=tag: judge.html_risk(container, t))
        for tag in container.tags if tag.type == "html" and tag.html
    ]
    jobs.append(("pii_exposure", lambda: judge.pii_exposure(container)))
    jobs.append(("naming_coherence", lambda: judge.naming_coherence(container)))

    findings: list[Finding] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn): label for label, fn in jobs}
        for future in as_completed(futures):
            label = futures[future]
            try:
                if finding := future.result():
                    findings.append(finding)
            except LLMError as exc:
                # One failed judgment must not lose the other five.
                _progress(f"  FAILED {label}: {exc}")

    # Deterministic order regardless of completion order, so runs are comparable.
    findings.sort(key=lambda f: (f.rule_id, f.entity_name))

    impact = judge.rank_by_impact(deterministic + findings)
    return findings, impact, judge.ledger


if __name__ == "__main__":
    import argparse

    from .parse import load
    from .rules import run_all

    ap = argparse.ArgumentParser(description="Run the LLM judgment layer.")
    ap.add_argument("container", nargs="?", default="data/sample_container.json")
    ap.add_argument("--vertical", default="healthcare clinic",
                    help="Site vertical — changes how third-party risk is judged.")
    args = ap.parse_args()

    load_dotenv()
    c = load(args.container)
    deterministic = run_all(c)

    try:
        llm_findings, impact, ledger = run(c, deterministic, args.vertical)
    except LLMError as exc:
        raise SystemExit(f"\n{exc}\n")

    print(f"{len(llm_findings)} LLM findings\n")
    for f in llm_findings:
        print(f"[{f.severity.upper():8}] {f.rule_id} {f.entity_name}")
        print(f"           {f.message}\n")

    # impact is keyed by index into this combined list — same order run() ranked.
    all_findings = deterministic + llm_findings

    print("Impact ranking (top 5):")
    for idx, meta in sorted(impact.items(), key=lambda kv: kv[1]["rank"])[:5]:
        f = all_findings[idx]
        print(f"  {meta['rank']}. [{meta['criterion']}] {f.rule_id} {f.entity_name}")
        print(f"     {meta['business_consequence']}")

    print("\nCost:", json.dumps(ledger.summary(), indent=2))
