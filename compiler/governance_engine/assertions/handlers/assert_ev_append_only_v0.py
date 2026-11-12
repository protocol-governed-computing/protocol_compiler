"""
ASSERT_EV_APPEND_ONLY_V0 Handler

Validates that EV artifacts do not declare mutation operation fields.
Events are append-only; mutation field names in the schema or extensions
are constitutional violations.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only
"""

_MUTATION_FIELDS = frozenset({"_update", "_delete", "_patch", "_mutate"})


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate EV artifacts do not contain mutation-signaling field names.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    ev_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "EV":
            continue

        ev_code = artifact.get("artifact_code", "UNKNOWN")
        ev_count += 1
        frontmatter = artifact.get("frontmatter", {})

        # Check core.schema field names
        schema = frontmatter.get("core", {}).get("schema", {})
        if isinstance(schema, dict):
            for field_name in schema:
                if field_name in _MUTATION_FIELDS:
                    violations.append({
                        "assert": "ASSERT_EV_APPEND_ONLY_V0",
                        "artifact": ev_code,
                        "field": field_name,
                        "violation": f"EV schema field '{field_name}' signals mutation; events are append-only",
                        "fix": f"Remove mutation field '{field_name}' from core.schema",
                    })

        # Check extensions block keys
        extensions = frontmatter.get("extensions", {})
        if isinstance(extensions, dict):
            for ext_key in extensions:
                if ext_key in _MUTATION_FIELDS:
                    violations.append({
                        "assert": "ASSERT_EV_APPEND_ONLY_V0",
                        "artifact": ev_code,
                        "field": ext_key,
                        "violation": f"EV extensions key '{ext_key}' signals mutation; events are append-only",
                        "fix": f"Remove mutation key '{ext_key}' from extensions",
                    })

    return {
        "assert_count": ev_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
