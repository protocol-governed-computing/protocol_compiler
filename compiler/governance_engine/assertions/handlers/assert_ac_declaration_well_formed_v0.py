"""
ASSERT_AC_DECLARATION_WELL_FORMED_V0 Handler

An actor declares identity and nothing else. Checks, over AC artifacts:

  1. core.type is an entry of the governed actor type vocabulary, `actor::VOCAB_ACTOR_TYPES_V0`
  2. every core.attributes entry declares an explicit type
  3. no execution / routing / side-effect key appears at any depth
  4. attribute values are literals, not runtime path expressions
"""

from typing import Any

RULE = "actor::INVARIANT_AC_DECLARATION_WELL_FORMED_V0"

# Read by its exact identity, never searched for: a domain build sees it as imported governance.
ACTOR_TYPES = "actor::VOCAB_ACTOR_TYPES_V0"
ACTOR_TYPE_GROUP = "actor_type"

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


def _actor_types(artifacts: list[dict]) -> set[str] | None:
    """The governed actor types, or None when this build cannot see the vocabulary."""
    for a in artifacts:
        if a.get("fqdn_id") == ACTOR_TYPES:
            group = (a.get("frontmatter", {}) or {}).get(ACTOR_TYPE_GROUP) or {}
            return set(group.get("entries") or [])
    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations: list[dict] = []
    actors = [a for a in artifacts if a.get("artifact_type") == "AC"]
    types = _actor_types(artifacts)
    if actors and types is None:
        violations.append({
            "fqdn": ACTOR_TYPES, "rule": RULE,
            "message": f"this build declares actors and cannot see {ACTOR_TYPES}",
            "fix": "Import the platform surface, which declares the actor type vocabulary"})

    for ac in actors:
        fqdn = ac.get("fqdn_id", "unknown")
        fm = ac.get("frontmatter", {}) or {}
        core = fm.get("core", {}) or {}

        def flag(message: str, fix: str) -> None:
            violations.append({"fqdn": fqdn, "rule": RULE, "message": message, "fix": fix})

        declared = str(core.get("type") or "").strip()
        if not declared:
            flag("actor declares no core.type",
                 "Declare core.type from the governed actor type vocabulary")
        elif types is not None and declared not in types:
            flag(f"actor type '{declared}' is not in {ACTOR_TYPES}",
                 f"Declare one of: {', '.join(sorted(types))}")

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
