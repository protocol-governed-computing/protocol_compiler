"""
ASSERT_IN_SCHEMA_REQUIRED_V0 Handler

Validates that every IN artifact declares a non-empty inputs block with typed fields.
IN artifacts declare inputs under core.inputs (not a top-level schema field).

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all IN artifacts have a non-empty, typed core.inputs declaration.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused; all data from artifacts)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    in_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "IN":
            continue

        in_code = artifact.get("artifact_code", "UNKNOWN")
        in_count += 1

        core = artifact.get("frontmatter", {}).get("core", {})
        inputs = core.get("inputs")

        if inputs is None:
            violations.append({
                "assert": "ASSERT_IN_SCHEMA_REQUIRED_V0",
                "artifact": in_code,
                "violation": "IN artifact must declare core.inputs",
                "fix": "Add core.inputs with at least one typed field declaration",
            })
            continue

        if not isinstance(inputs, dict) or len(inputs) == 0:
            violations.append({
                "assert": "ASSERT_IN_SCHEMA_REQUIRED_V0",
                "artifact": in_code,
                "violation": "IN core.inputs must declare at least one field",
                "fix": "Declare at least one input field under core.inputs",
            })
            continue

        for field_name, field_def in inputs.items():
            if not isinstance(field_def, dict):
                continue
            field_type = field_def.get("type")
            if not field_type:
                violations.append({
                    "assert": "ASSERT_IN_SCHEMA_REQUIRED_V0",
                    "artifact": in_code,
                    "field": field_name,
                    "violation": f"Input field '{field_name}' must declare a non-empty type",
                    "fix": f"Add type declaration to field '{field_name}'",
                })

    return {
        "assert_count": in_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
