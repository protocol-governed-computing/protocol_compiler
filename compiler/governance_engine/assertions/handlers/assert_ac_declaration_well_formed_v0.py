"""
ASSERT_AC_DECLARATION_WELL_FORMED_V0 Handler

An actor declares identity and nothing else. Checks, over AC artifacts:

  1. core.type is declared and non-empty
  2. every core.attributes entry declares an explicit type
  3. no execution / routing / side-effect key appears at any depth
  4. attribute values are literals, not runtime path expressions
"""

from typing import Any

RULE = "actor::INVARIANT_AC_DECLARATION_WELL_FORMED_V0"

FORBIDDEN_KEYS = frozenset({
    "implementation", "pipeline", "steps", "operations",
    "side_effects", "transforms", "bindings", "next", "on_result",
})


def _forbidden_paths(data: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if k in FORBIDDEN_KEYS:
                found.append(path)
            found.extend(_forbidden_paths(v, path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(_forbidden_paths(item, f"{prefix}[{i}]"))
    return found


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []
    actors = [a for a in artifacts if a.get("artifact_type") == "AC"]

    for ac in actors:
        fqdn = ac.get("fqdn_id", "unknown")
        fm = ac.get("frontmatter", {}) or {}
        core = fm.get("core", {}) or {}

        def flag(message: str, fix: str) -> None:
            violations.append({"fqdn": fqdn, "rule": RULE, "message": message, "fix": fix})

        if not str(core.get("type") or "").strip():
            flag("actor declares no core.type",
                 "Declare core.type from the governed actor type vocabulary")

        attributes = core.get("attributes")
        if isinstance(attributes, dict):
            for name, spec in attributes.items():
                if not isinstance(spec, dict) or not str(spec.get("type") or "").strip():
                    flag(f"attribute '{name}' declares no type",
                         f"Give core.attributes.{name} an explicit type")
                elif isinstance(spec.get("value"), str) and spec["value"].startswith("$."):
                    flag(f"attribute '{name}' resolves from runtime state: {spec['value']}",
                         "Declare a literal value; identity is a compile-time governed fact")

        for path in _forbidden_paths(fm):
            flag(f"actor declares execution surface at '{path}'",
                 "An actor declares identity and attributes only; move behaviour to a CC/CT/CS")

    return {
        "assert_count": len(actors),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
