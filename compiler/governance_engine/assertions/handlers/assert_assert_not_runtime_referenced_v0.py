"""
ASSERT_ASSERT_NOT_RUNTIME_REFERENCED_V0 Handler

The compile/execute boundary is one-way. ASSERTs read the compiled graph; nothing in
the compiled graph may reference an ASSERT. Scans executable artifacts (WF, CC, CS, CT,
RB) for any ASSERT_ code at any depth of the machine block.
"""

import re
from typing import Any

RULE = "conformance::INVARIANT_ASSERT_NOT_RUNTIME_REFERENCED_V0"

EXECUTABLE = frozenset({"WF", "CC", "CS", "CT", "RB"})
ASSERT_CODE = re.compile(r"\bASSERT_[A-Z0-9_]+_V[0-9]+\b")


def _assert_refs(data: Any, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            found.extend(_assert_refs(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(_assert_refs(item, f"{prefix}[{i}]"))
    elif isinstance(data, str):
        for m in ASSERT_CODE.findall(data):
            found.append((prefix, m))
    return found


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []
    subjects = [a for a in artifacts if a.get("artifact_type") in EXECUTABLE]

    for art in subjects:
        for path, code in _assert_refs(art.get("frontmatter", {}) or {}):
            violations.append({
                "fqdn": art.get("fqdn_id", "unknown"),
                "rule": RULE,
                "message": f"executable artifact references {code} at '{path}'",
                "fix": "Remove the ASSERT reference; governance is not reachable from execution",
            })

    return {
        "assert_count": len(subjects),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
