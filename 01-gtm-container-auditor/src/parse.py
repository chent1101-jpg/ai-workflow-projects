"""Parse a GTM container export into an object graph with resolved references.

No LLM involvement. Everything here is deterministic structure — the audit rules
in `rules.py` operate on this graph, and the model in `judge.py` only sees the
narrow slices that genuinely need judgment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VAR_REF = re.compile(r"\{\{([^}]+)\}\}")

# Trigger IDs at or above this value are GTM built-ins, not user-defined.
BUILTIN_TRIGGER_FLOOR = 2147479553
BUILTIN_TRIGGER_NAMES = {
    "2147479553": "All Pages",
    "2147479572": "All Elements (Click)",
    "2147479573": "All Links (Click)",
}

# Tag types that write to a Google Analytics destination, grouped by platform.
PLATFORM_BY_TAG_TYPE = {
    "googtag": "ga4",
    "gaawc": "ga4",
    "gaawe": "ga4",
    "ua": "universal_analytics",
    "html": "custom_html",
    "img": "custom_image",
}

DEPRECATED_TAG_TYPES = {"ua", "gas"}


def flatten_parameters(params: list[dict] | None) -> dict[str, Any]:
    """Collapse GTM's typed parameter list into a plain nested dict."""
    out: dict[str, Any] = {}
    for param in params or []:
        out[param.get("key", "")] = _flatten_value(param)
    return out


def _flatten_value(param: dict) -> Any:
    ptype = param.get("type")
    if ptype == "LIST":
        return [_flatten_value(item) for item in param.get("list", [])]
    if ptype == "MAP":
        return {m.get("key", ""): _flatten_value(m) for m in param.get("map", [])}
    return param.get("value")


def _collect_strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _collect_strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _collect_strings(v)]
    return []


@dataclass
class Tag:
    tag_id: str
    name: str
    type: str
    params: dict[str, Any]
    firing_trigger_ids: list[str]
    blocking_trigger_ids: list[str]
    paused: bool
    consent_status: str
    firing_option: str
    raw: dict

    @property
    def platform(self) -> str:
        return PLATFORM_BY_TAG_TYPE.get(self.type, "other")

    @property
    def referenced_variables(self) -> set[str]:
        return {
            m.strip()
            for s in _collect_strings(self.params)
            for m in VAR_REF.findall(s)
        }

    @property
    def html(self) -> str:
        return self.params.get("html", "") or ""

    @property
    def ga4_event_name(self) -> str | None:
        return self.params.get("eventName")

    @property
    def destination_id(self) -> str | None:
        """The measurement / tracking ID this tag sends to, if resolvable."""
        for key in ("tagId", "measurementIdOverride", "trackingId"):
            value = self.params.get(key)
            if isinstance(value, str) and value and not VAR_REF.search(value):
                return value
        return None


@dataclass
class Trigger:
    trigger_id: str
    name: str
    type: str
    filters: list[dict]
    params: dict[str, Any]
    raw: dict

    @property
    def referenced_variables(self) -> set[str]:
        strings = _collect_strings(self.params) + _collect_strings(self.filters)
        return {m.strip() for s in strings for m in VAR_REF.findall(s)}

    def filter_conditions(self) -> list[tuple[str, str, str]]:
        """(left_operand, operator, right_operand) for each filter clause."""
        out = []
        for f in self.filters:
            p = flatten_parameters(f.get("parameter"))
            out.append((p.get("arg0", ""), f.get("type", ""), p.get("arg1", "")))
        return out


@dataclass
class Variable:
    variable_id: str
    name: str
    type: str
    params: dict[str, Any]
    raw: dict

    @property
    def referenced_variables(self) -> set[str]:
        return {
            m.strip()
            for s in _collect_strings(self.params)
            for m in VAR_REF.findall(s)
        }


@dataclass
class Container:
    name: str
    public_id: str
    tags: list[Tag] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    builtin_variables: list[str] = field(default_factory=list)

    # --- lookups -----------------------------------------------------------
    @property
    def triggers_by_id(self) -> dict[str, Trigger]:
        return {t.trigger_id: t for t in self.triggers}

    @property
    def variables_by_name(self) -> dict[str, Variable]:
        return {v.name: v for v in self.variables}

    @property
    def known_variable_names(self) -> set[str]:
        return set(self.variables_by_name) | set(self.builtin_variables)

    def trigger_name(self, trigger_id: str) -> str:
        if trigger_id in self.triggers_by_id:
            return self.triggers_by_id[trigger_id].name
        if is_builtin_trigger(trigger_id):
            return BUILTIN_TRIGGER_NAMES.get(trigger_id, f"Built-in Trigger {trigger_id}")
        return f"<missing trigger {trigger_id}>"

    def tags_for_trigger(self, trigger_id: str) -> list[Tag]:
        return [t for t in self.tags if trigger_id in t.firing_trigger_ids]

    @property
    def all_referenced_trigger_ids(self) -> set[str]:
        ids: set[str] = set()
        for tag in self.tags:
            ids.update(tag.firing_trigger_ids)
            ids.update(tag.blocking_trigger_ids)
        return ids

    @property
    def all_referenced_variable_names(self) -> set[str]:
        names: set[str] = set()
        for item in (*self.tags, *self.triggers, *self.variables):
            names.update(item.referenced_variables)
        return names

    def summary(self) -> dict[str, int]:
        return {
            "tags": len(self.tags),
            "triggers": len(self.triggers),
            "user_variables": len(self.variables),
            "builtin_variables": len(self.builtin_variables),
        }


def is_builtin_trigger(trigger_id: str) -> bool:
    return trigger_id.isdigit() and int(trigger_id) >= BUILTIN_TRIGGER_FLOOR


def load(path: str | Path) -> Container:
    data = json.loads(Path(path).read_text())
    version = data.get("containerVersion", data)
    meta = version.get("container", {})

    tags = [
        Tag(
            tag_id=t.get("tagId", ""),
            name=t.get("name", ""),
            type=t.get("type", ""),
            params=flatten_parameters(t.get("parameter")),
            firing_trigger_ids=list(t.get("firingTriggerId", [])),
            blocking_trigger_ids=list(t.get("blockingTriggerId", [])),
            paused=bool(t.get("paused", False)),
            consent_status=(t.get("consentSettings") or {}).get("consentStatus", "NOT_SET"),
            firing_option=t.get("tagFiringOption", ""),
            raw=t,
        )
        for t in version.get("tag", [])
    ]

    triggers = [
        Trigger(
            trigger_id=t.get("triggerId", ""),
            name=t.get("name", ""),
            type=t.get("type", ""),
            filters=list(t.get("filter", [])),
            params=flatten_parameters(t.get("parameter")),
            raw=t,
        )
        for t in version.get("trigger", [])
    ]

    variables = [
        Variable(
            variable_id=v.get("variableId", ""),
            name=v.get("name", ""),
            type=v.get("type", ""),
            params=flatten_parameters(v.get("parameter")),
            raw=v,
        )
        for v in version.get("variable", [])
    ]

    return Container(
        name=meta.get("name", "unknown"),
        public_id=meta.get("publicId", "unknown"),
        tags=tags,
        triggers=triggers,
        variables=variables,
        builtin_variables=[b.get("name", "") for b in version.get("builtInVariable", [])],
    )


if __name__ == "__main__":
    import sys

    c = load(sys.argv[1] if len(sys.argv) > 1 else "data/sample_container.json")
    print(f"{c.name} ({c.public_id})")
    for k, v in c.summary().items():
        print(f"  {k}: {v}")
