"""Deterministic audit rules.

Every check in this file is decidable by inspecting the container graph. No LLM
is involved and none should be added here — if a question has a right answer that
code can compute, code computes it. Judgment calls live in `judge.py`.

Each rule is a function taking a Container and yielding Findings. Rules are
registered by decorator so `evals/` can score them individually.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterator

from .parse import Container, DEPRECATED_TAG_TYPES, Tag, is_builtin_trigger

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class Finding:
    rule_id: str
    severity: str
    category: str
    entity_type: str
    entity_name: str
    message: str
    remediation: str = ""
    evidence: dict = field(default_factory=dict)
    source: str = "deterministic"

    def to_dict(self) -> dict:
        return asdict(self)


RuleFn = Callable[[Container], Iterator[Finding]]
REGISTRY: dict[str, RuleFn] = {}


def rule(rule_id: str) -> Callable[[RuleFn], RuleFn]:
    def wrap(fn: RuleFn) -> RuleFn:
        fn.rule_id = rule_id  # type: ignore[attr-defined]
        REGISTRY[rule_id] = fn
        return fn

    return wrap


# --- Reference integrity ----------------------------------------------------


@rule("GTM001")
def orphaned_trigger(c: Container) -> Iterator[Finding]:
    """A user-defined trigger no tag fires on — dead config or a broken hookup."""
    referenced = c.all_referenced_trigger_ids
    for trigger in c.triggers:
        if trigger.trigger_id not in referenced:
            yield Finding(
                "GTM001", "medium", "reference_integrity", "trigger", trigger.name,
                f"Trigger '{trigger.name}' ({trigger.type}) is not referenced by any tag.",
                "Delete the trigger, or attach the tag it was built for.",
                {"trigger_id": trigger.trigger_id, "trigger_type": trigger.type},
            )


@rule("GTM002")
def tag_without_trigger(c: Container) -> Iterator[Finding]:
    """A tag with no firing trigger can never fire."""
    for tag in c.tags:
        if not tag.firing_trigger_ids:
            yield Finding(
                "GTM002", "high", "reference_integrity", "tag", tag.name,
                f"Tag '{tag.name}' has no firing trigger and will never fire.",
                "Attach a firing trigger or delete the tag.",
                {"tag_id": tag.tag_id, "tag_type": tag.type},
            )


@rule("GTM003")
def missing_trigger_reference(c: Container) -> Iterator[Finding]:
    """A tag pointing at a trigger ID that does not exist in the container."""
    known = set(c.triggers_by_id)
    for tag in c.tags:
        for tid in tag.firing_trigger_ids + tag.blocking_trigger_ids:
            if tid not in known and not is_builtin_trigger(tid):
                yield Finding(
                    "GTM003", "critical", "reference_integrity", "tag", tag.name,
                    f"Tag '{tag.name}' references trigger ID {tid}, which does not exist.",
                    "Repoint the tag at a valid trigger.",
                    {"tag_id": tag.tag_id, "missing_trigger_id": tid},
                )


@rule("GTM004")
def missing_variable_reference(c: Container) -> Iterator[Finding]:
    """A {{Variable}} reference with no matching user or built-in variable."""
    known = c.known_variable_names
    for kind, items in (("tag", c.tags), ("trigger", c.triggers), ("variable", c.variables)):
        for item in items:
            for name in sorted(item.referenced_variables - known):
                yield Finding(
                    "GTM004", "critical", "reference_integrity", kind, item.name,
                    f"{kind.title()} '{item.name}' references undefined variable "
                    f"{{{{{name}}}}}, which resolves to undefined at runtime.",
                    "Create the variable or enable the corresponding built-in.",
                    {"missing_variable": name},
                )


@rule("GTM005")
def unused_variable(c: Container) -> Iterator[Finding]:
    """A user-defined variable nothing references."""
    referenced = c.all_referenced_variable_names
    for var in c.variables:
        if var.name not in referenced:
            yield Finding(
                "GTM005", "low", "hygiene", "variable", var.name,
                f"Variable '{var.name}' ({var.type}) is not referenced anywhere.",
                "Delete it, or wire it into the tag it was built for.",
                {"variable_id": var.variable_id, "variable_type": var.type},
            )


# --- Deprecation and platform health ----------------------------------------


@rule("GTM006")
def deprecated_universal_analytics(c: Container) -> Iterator[Finding]:
    """Universal Analytics stopped processing data on 2023-07-01."""
    for tag in c.tags:
        if tag.type in DEPRECATED_TAG_TYPES:
            yield Finding(
                "GTM006", "high", "deprecation", "tag", tag.name,
                f"Tag '{tag.name}' is a Universal Analytics tag. UA stopped processing "
                "hits on 2023-07-01; this tag adds page weight and collects nothing.",
                "Delete the tag once GA4 coverage for this event is confirmed.",
                {"tag_id": tag.tag_id, "tag_type": tag.type},
            )
    for var in c.variables:
        tracking_id = var.params.get("trackingId", "")
        if var.type in DEPRECATED_TAG_TYPES or (
            isinstance(tracking_id, str) and tracking_id.startswith("UA-")
        ):
            yield Finding(
                "GTM006", "high", "deprecation", "variable", var.name,
                f"Variable '{var.name}' holds Universal Analytics settings "
                f"({tracking_id or var.type}), which no longer collect data.",
                "Remove after the dependent UA tags are deleted.",
                {"variable_id": var.variable_id, "tracking_id": tracking_id},
            )


@rule("GTM007")
def consent_not_configured(c: Container) -> Iterator[Finding]:
    """Tags with no consent settings fire regardless of consent state."""
    unset = [t for t in c.tags if t.consent_status == "NOT_SET"]
    if not unset:
        return
    marketing = [t for t in unset if t.platform in ("custom_html", "custom_image")]
    severity = "critical" if marketing else "high"
    yield Finding(
        "GTM007", severity, "privacy", "container", c.name,
        f"{len(unset)} of {len(c.tags)} tags have consentStatus NOT_SET — no tag in "
        "this container is gated on consent. Includes "
        f"{len(marketing)} custom HTML/image tag(s), which are the highest-risk category.",
        "Configure Consent Mode and set additional consent checks on marketing tags.",
        {
            "tags_without_consent": len(unset),
            "total_tags": len(c.tags),
            "ungated_custom_html": [t.name for t in marketing],
        },
    )


# --- Data quality ------------------------------------------------------------


@rule("GTM008")
def duplicate_tag_name(c: Container) -> Iterator[Finding]:
    counts = Counter(t.name for t in c.tags)
    for name, n in counts.items():
        if n > 1:
            yield Finding(
                "GTM008", "medium", "hygiene", "tag", name,
                f"{n} tags share the name '{name}', making debugging ambiguous.",
                "Rename to unique, convention-following names.",
                {"occurrences": n},
            )


@rule("GTM009")
def duplicate_conversion_risk(c: Container) -> Iterator[Finding]:
    """Multiple GA4 event tags on one trigger record several events per user action.

    Keyed per trigger, not per identical trigger set: a tag firing on {A} and a tag
    firing on {A, B} still both fire on A, which is the case that inflates counts.
    """
    groups: dict[tuple[str | None, str], list[Tag]] = defaultdict(list)
    for tag in c.tags:
        if tag.type != "gaawe":
            continue
        for trigger_id in tag.firing_trigger_ids:
            groups[(tag.destination_id, trigger_id)].append(tag)

    reported: set[frozenset[str]] = set()
    for (destination, trigger_id), tags in sorted(groups.items(), key=lambda kv: kv[0][1]):
        events = sorted({t.ga4_event_name or t.name for t in tags})
        if len(tags) < 2 or len(events) < 2:
            continue
        key = frozenset(t.tag_id for t in tags)
        if key in reported:
            continue
        reported.add(key)
        yield Finding(
            "GTM009", "high", "data_quality", "tag", ", ".join(t.name for t in tags),
            f"{len(tags)} GA4 event tags fire on trigger '{c.trigger_name(trigger_id)}' and "
            f"send to the same destination {destination}. Events {events} are all recorded "
            "for a single user action, inflating conversion counts and double-counting any "
            "of them marked as a key event.",
            "Keep one canonical event; differentiate with an event parameter instead of a second tag.",
            {
                "tags": [t.name for t in tags],
                "events": events,
                "destination": destination,
                "shared_trigger": c.trigger_name(trigger_id),
            },
        )


@rule("GTM010")
def multiple_config_tags_same_trigger(c: Container) -> Iterator[Finding]:
    """More than one GA4 config tag on the same trigger — usually unintended."""
    groups: dict[frozenset, list[Tag]] = defaultdict(list)
    for tag in c.tags:
        if tag.type == "googtag":
            groups[frozenset(tag.firing_trigger_ids)].append(tag)
    for trigger_ids, tags in groups.items():
        if len(tags) < 2:
            continue
        yield Finding(
            "GTM010", "medium", "data_quality", "tag", ", ".join(t.name for t in tags),
            f"{len(tags)} GA4 configuration tags fire on the same trigger "
            f"({', '.join(c.trigger_name(t) for t in sorted(trigger_ids))}), sending "
            f"duplicate page_view hits to {[t.destination_id for t in tags]}.",
            "Confirm this is an intentional roll-up property; otherwise remove the duplicate.",
            {"tags": [t.name for t in tags], "destinations": [t.destination_id for t in tags]},
        )


@rule("GTM011")
def overlapping_trigger_conditions(c: Container) -> Iterator[Finding]:
    """CONTAINS filters where one match value is a substring of another."""
    page_vars = {"{{Page URL}}", "{{Page Path}}", "{{Page Hostname}}"}
    conditions = []
    for trigger in c.triggers:
        for left, op, right in trigger.filter_conditions():
            if left in page_vars and op == "CONTAINS" and right:
                conditions.append((trigger, left, right))

    for a_trigger, a_left, a_val in conditions:
        for b_trigger, b_left, b_val in conditions:
            if a_trigger.trigger_id >= b_trigger.trigger_id or a_val == b_val:
                continue
            if a_val in b_val or b_val in a_val:
                broad, narrow = (a_val, b_val) if len(a_val) < len(b_val) else (b_val, a_val)
                yield Finding(
                    "GTM011", "medium", "data_quality", "trigger",
                    f"{a_trigger.name} / {b_trigger.name}",
                    f"Triggers '{a_trigger.name}' and '{b_trigger.name}' use overlapping "
                    f"CONTAINS conditions ('{broad}' also matches '{narrow}'), so both fire "
                    "on the same pageview.",
                    "Use EQUALS or a regex anchor so the conditions are mutually exclusive.",
                    {"broad_match": broad, "narrow_match": narrow,
                     "variables": sorted({a_left, b_left})},
                )


@rule("GTM012")
def inconsistent_page_variable(c: Container) -> Iterator[Finding]:
    """Path-shaped matches tested against Page URL behave differently than Page Path."""
    for trigger in c.triggers:
        for left, op, right in trigger.filter_conditions():
            if left == "{{Page URL}}" and op == "CONTAINS" and right and "." not in right:
                yield Finding(
                    "GTM012", "low", "data_quality", "trigger", trigger.name,
                    f"Trigger '{trigger.name}' matches '{right}' against {{{{Page URL}}}}, "
                    "which includes protocol, hostname and query string. Sibling triggers "
                    "in this container match the same style of value against {{Page Path}}.",
                    "Standardize on {{Page Path}} for path matching to avoid query-string false positives.",
                    {"match_value": right},
                )


# --- Custom HTML risk surface ------------------------------------------------

HARDCODED_PATTERNS = [
    (r"\bUA-\d{4,}-\d+\b", "Universal Analytics ID"),
    (r"\bG-[A-Z0-9]{8,}\b", "GA4 measurement ID"),
    (r"\bGTM-[A-Z0-9]{6,}\b", "GTM container ID"),
    (r"\bAW-\d{9,}\b", "Google Ads conversion ID"),
    (r"\b\d{3}-\d{3}-\d{4}\b", "phone number"),
    (r"[\w.+-]+@[\w-]+\.[\w.]{2,}", "email address"),
]


@rule("GTM013")
def hardcoded_values_in_custom_html(c: Container) -> Iterator[Finding]:
    """Identifiers hardcoded in custom HTML can't be swapped per environment."""
    for tag in c.tags:
        if tag.type != "html" or not tag.html:
            continue
        hits = []
        for pattern, label in HARDCODED_PATTERNS:
            for match in set(re.findall(pattern, tag.html)):
                hits.append(f"{label}: {match}")
        if hits:
            yield Finding(
                "GTM013", "medium", "maintainability", "tag", tag.name,
                f"Custom HTML tag '{tag.name}' hardcodes {len(hits)} identifier(s) that "
                "should be variables: " + "; ".join(sorted(hits)),
                "Move each value into a GTM variable so staging and production can differ.",
                {"tag_id": tag.tag_id, "hardcoded": sorted(hits)},
            )


@rule("GTM014")
def malformed_css_selector(c: Container) -> Iterator[Finding]:
    """An Element Visibility selector that looks like a copied class attribute."""
    for trigger in c.triggers:
        selector = trigger.params.get("elementSelector")
        if not isinstance(selector, str) or not selector.strip():
            continue
        if trigger.params.get("selectorType") != "CSS":
            continue
        tokens = selector.split()
        bare = [t for t in tokens[1:] if not t[0] in ".#[:>+~*"]
        if len(tokens) > 1 and bare:
            yield Finding(
                "GTM014", "high", "correctness", "trigger", trigger.name,
                f"Trigger '{trigger.name}' uses CSS selector '{selector}'. The "
                f"space-separated token(s) {bare} have no leading '.', so CSS reads them as "
                "descendant element types rather than classes. This selector matches nothing.",
                "Prefix each class with '.' and remove spaces: "
                + "".join("." + t.lstrip(".") for t in tokens),
                {"selector": selector, "unprefixed_tokens": bare},
            )


@rule("GTM015")
def naming_convention_drift(c: Container) -> Iterator[Finding]:
    """Mixed platform-suffix conventions make bulk operations unreliable."""
    patterns = {
        "dash_suffix": re.compile(r"\s-\s(GA4|GA|UA)$"),
        "paren_suffix": re.compile(r"\((GA4|GA|UA)\)$"),
    }
    matched = {k: [t.name for t in c.tags if p.search(t.name)] for k, p in patterns.items()}
    used = {k: v for k, v in matched.items() if v}
    if len(used) > 1:
        minority = min(used, key=lambda k: len(used[k]))
        yield Finding(
            "GTM015", "low", "hygiene", "container", c.name,
            "Tag names mix platform-suffix conventions: "
            + "; ".join(f"{k} ({len(v)} tags)" for k, v in used.items())
            + ". Bulk find/replace and naming-based filters will miss tags.",
            f"Standardize on the majority convention; {len(used[minority])} tag(s) deviate.",
            {k: v for k, v in used.items()},
        )

    mislabeled = [t.name for t in c.tags if re.search(r"\bTrigger\b", t.name)]
    if mislabeled:
        yield Finding(
            "GTM015", "low", "hygiene", "tag", ", ".join(mislabeled),
            f"{len(mislabeled)} tag(s) have 'Trigger' in the name, which describes the "
            "wrong entity type and misleads anyone scanning the tag list.",
            "Rename to describe what the tag sends, not what fires it.",
            {"tags": mislabeled},
        )


@rule("GTM016")
def paused_tag(c: Container) -> Iterator[Finding]:
    for tag in c.tags:
        if tag.paused:
            yield Finding(
                "GTM016", "info", "hygiene", "tag", tag.name,
                f"Tag '{tag.name}' is paused and collects nothing.",
                "Delete if obsolete; unpause if it was paused for a temporary reason.",
                {"tag_id": tag.tag_id},
            )


def run_all(container: Container, only: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, fn in REGISTRY.items():
        if only and rule_id not in only:
            continue
        findings.extend(fn(container))
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.rule_id, f.entity_name))
    return findings


if __name__ == "__main__":
    import sys
    from .parse import load

    c = load(sys.argv[1] if len(sys.argv) > 1 else "data/sample_container.json")
    results = run_all(c)
    print(f"{len(results)} deterministic findings across {len(REGISTRY)} rules\n")
    for f in results:
        print(f"[{f.severity.upper():8}] {f.rule_id} {f.entity_type}: {f.entity_name}")
        print(f"           {f.message}\n")
