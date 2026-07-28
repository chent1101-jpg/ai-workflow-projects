"""Provider-agnostic LLM client with schema enforcement and cost tracking.

Routes through OpenRouter so a single key reaches open-weight models (GLM, Kimi,
DeepSeek) and frontier models (Claude, GPT) behind one endpoint. That makes the
model-comparison eval in project 06 nearly free to run, and it means routing
decisions can be measured rather than asserted.

Standard library only — no pip install required to run any project's rules or
judge layer.

Design notes:
  * Model slugs are resolved against OpenRouter's live /models endpoint rather
    than hardcoded, because slugs carry date suffixes that change on release.
  * Pricing is read from the same endpoint, so cost figures are current rather
    than copied from a blog post.
  * Schema violations are counted, not just retried. How often a model returns
    malformed structured output is the metric that decides whether a cheap model
    is usable for a given task — it belongs in the eval, not in a silent except.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MODEL_CACHE = Path.home() / ".cache" / "ai-workflow-projects" / "openrouter_models.json"
MODEL_CACHE_TTL_SECONDS = 86_400

# Short aliases so project code and .env files don't carry dated slugs.
# Resolved to real slugs at runtime; a stale alias fails loudly with candidates.
ALIASES = {
    "glm": "z-ai/glm-5.2",
    "kimi": "moonshotai/kimi-k2.6",
    "deepseek": "deepseek/deepseek-v4-flash",
    "haiku": "anthropic/claude-haiku-4.5",
    "sonnet": "anthropic/claude-sonnet-5",
    "opus": "anthropic/claude-opus-5",
}


def _progress(message: str, end: str = "\n") -> None:
    """Per-call progress to stderr. A multi-call audit should never be a black box.
    Silence with QUIET=1."""
    if not os.environ.get("QUIET"):
        print(message, end=end, file=sys.stderr, flush=True)


class LLMError(RuntimeError):
    pass


class SchemaViolation(LLMError):
    """Model returned JSON that does not satisfy the requested schema."""


# --- environment -------------------------------------------------------------


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader. Avoids a python-dotenv dependency."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# --- model registry ----------------------------------------------------------


def _fetch_models() -> list[dict]:
    if MODEL_CACHE.exists():
        age = time.time() - MODEL_CACHE.stat().st_mtime
        if age < MODEL_CACHE_TTL_SECONDS:
            return json.loads(MODEL_CACHE.read_text())["data"]

    with urllib.request.urlopen(f"{OPENROUTER_BASE}/models", timeout=30) as resp:
        payload = json.loads(resp.read())

    MODEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    MODEL_CACHE.write_text(json.dumps(payload))
    return payload["data"]


@dataclass
class ModelInfo:
    slug: str
    prompt_usd_per_token: float
    completion_usd_per_token: float
    context_length: int
    supports_structured_outputs: bool
    supports_tools: bool

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.prompt_usd_per_token
            + completion_tokens * self.completion_usd_per_token
        )


def resolve_model(name: str) -> ModelInfo:
    """Resolve an alias or partial slug to a live OpenRouter model.

    Slugs carry date suffixes (`z-ai/glm-5.2-20260616`) that change on release,
    so this prefix-matches rather than requiring an exact string.
    """
    target = ALIASES.get(name, name)
    models = _fetch_models()

    exact = [m for m in models if m["id"] == target]
    prefixed = [m for m in models if m["id"].startswith(target)]
    matches = exact or prefixed

    if not matches:
        near = sorted(m["id"] for m in models if target.split("/")[-1][:6] in m["id"])
        raise LLMError(
            f"No OpenRouter model matching {target!r}.\n"
            + ("Did you mean:\n  " + "\n  ".join(near[:8]) if near else "No near matches.")
        )

    # Prefer the newest dated variant when several match.
    m = sorted(matches, key=lambda x: x["id"])[-1]
    pricing = m.get("pricing", {})
    params = m.get("supported_parameters", []) or []
    return ModelInfo(
        slug=m["id"],
        prompt_usd_per_token=float(pricing.get("prompt", 0) or 0),
        completion_usd_per_token=float(pricing.get("completion", 0) or 0),
        context_length=int(m.get("context_length", 0) or 0),
        supports_structured_outputs="structured_outputs" in params,
        supports_tools="tools" in params,
    )


# --- usage accounting --------------------------------------------------------


@dataclass
class Call:
    model: str
    task: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_s: float
    attempts: int
    schema_violations: int


@dataclass
class Ledger:
    """Per-run accounting. Every project must be able to answer 'what did this cost?'"""

    calls: list[Call] = field(default_factory=list)

    def add(self, call: Call) -> None:
        self.calls.append(call)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.prompt_tokens + c.completion_tokens for c in self.calls)

    @property
    def schema_violation_rate(self) -> float:
        attempts = sum(c.attempts for c in self.calls)
        return sum(c.schema_violations for c in self.calls) / attempts if attempts else 0.0

    def summary(self) -> dict:
        by_model: dict[str, dict] = {}
        for c in self.calls:
            entry = by_model.setdefault(c.model, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
            entry["calls"] += 1
            entry["tokens"] += c.prompt_tokens + c.completion_tokens
            entry["cost_usd"] = round(entry["cost_usd"] + c.cost_usd, 6)
        return {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "calls": len(self.calls),
            "schema_violation_rate": round(self.schema_violation_rate, 4),
            "by_model": by_model,
            "by_task": sorted({c.task for c in self.calls}),
        }


# --- minimal schema validation ----------------------------------------------

_TYPES = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool,
}


def validate(data: Any, schema: dict, path: str = "$") -> list[str]:
    """Validate required keys, types, and enums. Enough to catch a model that
    ignored the schema; deliberately not a full JSON Schema implementation."""
    errors: list[str] = []
    expected = schema.get("type")

    if expected and expected in _TYPES and not isinstance(data, _TYPES[expected]):
        # bool is a subclass of int — reject it where a number is required
        if not (expected in ("integer", "number") and isinstance(data, bool)):
            return [f"{path}: expected {expected}, got {type(data).__name__}"]
        return [f"{path}: expected {expected}, got bool"]

    if (enum := schema.get("enum")) and data not in enum:
        errors.append(f"{path}: {data!r} not in {enum}")

    if expected == "object":
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}.{key}: required key missing")
        for key, sub in (schema.get("properties") or {}).items():
            if key in data:
                errors.extend(validate(data[key], sub, f"{path}.{key}"))

    if expected == "array" and (items := schema.get("items")):
        for i, item in enumerate(data):
            errors.extend(validate(item, items, f"{path}[{i}]"))

    return errors


# --- client ------------------------------------------------------------------


class LLMClient:
    def __init__(self, model: str, ledger: Ledger | None = None, timeout: int = 120):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise LLMError(
                "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add "
                "your key from https://openrouter.ai/keys"
            )
        self.info = resolve_model(model)
        self.ledger = ledger if ledger is not None else Ledger()
        self.timeout = timeout

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        task: str,
        schema_name: str = "response",
        max_attempts: int = 3,
    ) -> dict:
        """Return schema-valid JSON, retrying with the validation errors fed back.

        Uses the provider's native structured-output mode when the model supports
        it, and falls back to prompt-level instruction plus client-side validation
        when it doesn't — which is why open-weight models remain usable here.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        body: dict[str, Any] = {"model": self.info.slug, "messages": messages}

        if self.info.supports_structured_outputs:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            }
        else:
            messages[0]["content"] += (
                "\n\nRespond with a single JSON object matching this schema exactly. "
                "No prose, no markdown fences.\n" + json.dumps(schema)
            )

        started = time.time()
        violations = 0
        last_errors: list[str] = []

        for attempt in range(1, max_attempts + 1):
            _progress(f"  {task} -> {self.info.slug} (attempt {attempt})... ", end="")
            raw, usage = self._post(body)
            parsed, errors = self._parse(raw, schema)

            if not errors:
                _progress(f"ok  {usage[0]}+{usage[1]} tok  "
                          f"${self.info.cost(*usage):.4f}  {time.time() - started:.1f}s")
                self.ledger.add(Call(
                    model=self.info.slug, task=task,
                    prompt_tokens=usage[0], completion_tokens=usage[1],
                    cost_usd=self.info.cost(*usage),
                    latency_s=round(time.time() - started, 2),
                    attempts=attempt, schema_violations=violations,
                ))
                return parsed

            violations += 1
            last_errors = errors
            _progress(f"SCHEMA VIOLATION ({len(errors)}): {errors[0]}")
            if attempt < max_attempts:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content":
                    "That response failed schema validation:\n"
                    + "\n".join(f"  - {e}" for e in errors)
                    + "\nReturn corrected JSON only."})

        self.ledger.add(Call(
            model=self.info.slug, task=task,
            prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
            latency_s=round(time.time() - started, 2),
            attempts=max_attempts, schema_violations=violations,
        ))
        raise SchemaViolation(
            f"{self.info.slug} failed schema validation for task {task!r} after "
            f"{max_attempts} attempts:\n" + "\n".join(f"  - {e}" for e in last_errors)
        )

    # -- internals ------------------------------------------------------------

    def _post(self, body: dict) -> tuple[str, tuple[int, int]]:
        request = urllib.request.Request(
            f"{OPENROUTER_BASE}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": "AI Workflow Projects",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise LLMError(f"OpenRouter {e.code}: {e.read().decode()[:500]}") from e

        if "error" in payload:
            raise LLMError(f"OpenRouter error: {payload['error']}")

        content = payload["choices"][0]["message"]["content"] or ""
        usage = payload.get("usage") or {}
        return content, (
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )

    @staticmethod
    def _parse(raw: str, schema: dict) -> tuple[dict, list[str]]:
        text = raw.strip()
        if text.startswith("```"):  # some models fence despite instructions
            text = text.split("```")[1].removeprefix("json").strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            return {}, [f"$: response is not valid JSON ({e})"]
        return parsed, validate(parsed, schema)


if __name__ == "__main__":
    import sys

    load_dotenv()
    for name in sys.argv[1:] or list(ALIASES):
        try:
            info = resolve_model(name)
            print(
                f"{name:10} -> {info.slug:38} "
                f"${info.prompt_usd_per_token * 1e6:>6.2f}/M in  "
                f"${info.completion_usd_per_token * 1e6:>6.2f}/M out  "
                f"ctx {info.context_length:>9,}  "
                f"structured={info.supports_structured_outputs}"
            )
        except LLMError as exc:
            print(f"{name:10} -> {exc}")
