"""Anonymize a real GTM container export so it can be committed publicly.

Two constraints drive the design:

1. **The mapping never enters version control.** Real identifiers live only in
   `data/private/anonymization_map.json` (gitignored). This file contains logic
   and generic detection patterns — no client values.
2. **Anonymization preserves every auditable defect.** Identifier *shape* is kept
   (`G-`, `UA-`, `GTM-`, phone format) so format-based rules fire identically on
   the public sample and the original. The reference graph is untouched.

Fails closed: if any mapped value or identifier-shaped string survives, nothing
is written.

Usage:
    python3 -m src.anonymize <input.json> <output.json> [map.json]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_MAP = Path("data/private/anonymization_map.json")

# Numeric config values inside custom HTML that identify a client or campaign.
NUMERIC_ID_KEYS = ("clientId", "campaignId", "defaultCampaignId")

# Generic leak detectors. These describe identifier *shapes*, not client values,
# so they are safe to commit. Each allows only the known-safe placeholder form.
LEAK_PATTERNS = [
    (r"\bUA-(?!11111111\b)\d{4,}-\d+\b", "unmapped Universal Analytics ID"),
    (r"\bG-(?!DEMO)[A-Z0-9]{8,}\b", "unmapped GA4 measurement ID"),
    (r"\bGTM-(?!EXAMPL1\b)[A-Z0-9]{6,}\b", "unmapped GTM container ID"),
    (r"\bAW-\d{9,}\b", "Google Ads conversion ID"),
    (r"[\w.+-]+@[\w-]+\.[\w.]{2,}", "email address"),
    (r"\b(?!555-010-0000\b)\d{3}-\d{3}-\d{4}\b", "unmapped phone number"),
]


def _fake_numeric(value: str) -> str:
    """Deterministic stand-in so repeat runs produce byte-identical output."""
    return str(10000 + int(hashlib.sha256(value.encode()).hexdigest()[:8], 16) % 90000)


def load_map(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    if not path.exists():
        raise SystemExit(
            f"Mapping file not found: {path}\n"
            "This file holds real client identifiers and is intentionally gitignored.\n"
            "See data/README.md for the expected schema."
        )
    data = json.loads(path.read_text())
    # Longest keys first so 'info.example.com' is replaced before 'example.com'.
    literal = dict(sorted(data.get("literal", {}).items(), key=lambda kv: -len(kv[0])))
    return literal, data.get("word", {})


def scrub_string(text: str, literal: dict[str, str], word: dict[str, str]) -> str:
    for real, fake in literal.items():
        text = text.replace(real, fake)
    for real, fake in word.items():
        text = re.sub(rf"\b{re.escape(real)}\b", fake, text)
    for key in NUMERIC_ID_KEYS:
        text = re.sub(
            rf"({re.escape(key)}\s*:\s*)(\d+)",
            lambda m: m.group(1) + _fake_numeric(m.group(2)),
            text,
        )
    return text


def scrub(node, literal: dict[str, str], word: dict[str, str]):
    if isinstance(node, dict):
        return {k: scrub(v, literal, word) for k, v in node.items()}
    if isinstance(node, list):
        return [scrub(v, literal, word) for v in node]
    if isinstance(node, str):
        return scrub_string(node, literal, word)
    return node


def find_leaks(raw: str, literal: dict[str, str], word: dict[str, str]) -> list[str]:
    leaks = []
    for real in list(literal) + list(word):
        if re.search(rf"(?<![\w-]){re.escape(real)}(?![\w-])", raw):
            leaks.append(f"mapped value survived: {real[:4]}…")
    for pattern, label in LEAK_PATTERNS:
        if re.search(pattern, raw):
            leaks.append(label)
    return leaks


def main() -> int:
    if not 3 <= len(sys.argv) <= 4:
        print(__doc__)
        return 2

    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    map_path = Path(sys.argv[3]) if len(sys.argv) == 4 else DEFAULT_MAP
    literal, word = load_map(map_path)

    scrubbed = scrub(json.loads(src.read_text()), literal, word)
    scrubbed["exportTime"] = "2026-01-01 00:00:00"
    raw = json.dumps(scrubbed, indent=4)

    leaks = find_leaks(raw, literal, word)
    if leaks:
        print("ANONYMIZATION FAILED — nothing written. Surviving identifiers:")
        for leak in sorted(set(leaks)):
            print(f"  - {leak}")
        return 1

    dst.write_text(raw + "\n")
    print(f"Wrote {dst} ({len(raw):,} bytes). {len(literal) + len(word)} mappings applied, "
          f"{len(LEAK_PATTERNS)} leak patterns clear.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
