"""
ASSERT_EV_SCHEMA_REQUIRED_V0 Handler

Validates that every EV (Event) artifact declares a non-empty core.schema block.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all EV artifacts have a non-empty core.schema declaration.

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

        core = artifact.get("frontmatter", {}).get("core", {})
        schema = core.get("schema")

        if schema is None:
            violations.append({
                "assert": "ASSERT_EV_SCHEMA_REQUIRED_V0",
                "artifact": ev_code,
                "violation": "EV artifact must declare core.schema",
                "fix": "Add core.schema with at least one typed field declaration",
            })
            continue

        if not isinstance(schema, dict) or len(schema) == 0:
            violations.append({
                "assert": "ASSERT_EV_SCHEMA_REQUIRED_V0",
                "artifact": ev_code,
                "violation": "EV core.schema must declare at least one field",
                "fix": "Declare at least one field under core.schema",
            })

    return {
        "assert_count": ev_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
