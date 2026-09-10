"""
ASSERT_SCHEMA_CONFORMANCE_V0 Handler

Validates that artifact frontmatter conforms to declared JSON schemas.
The compiler pre-computes schema validation per-node and relays results
via compilation_context["schema_conformance"].

CONSTITUTIONAL: Schema conformance is a compile-time invariant.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate schema conformance via pre-computed analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed schema_conformance

    Returns:
        Standardized result dict with assert_count, violations, status
    """
    violations = []
    check_count = 0

    conformance = compilation_context.get("schema_conformance")

    if conformance is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "artifact::ASSERT_SCHEMA_CONFORMANCE_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing schema_conformance",
                "fix": "Compiler must pre-compute schema validation before assert phase"
            }],
            "status": "FAILED"
        }

    for artifact in artifacts:
        fqdn = artifact.get("fqdn_id")
        if not fqdn:
            continue

        result = conformance.get(fqdn)
        if not result:
            continue

        check_count += 1

        if result.get("status") == "FAILED":
            for schema_error in result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "artifact::INVARIANT_SCHEMA_CONFORMANCE_V0",
                    "message": schema_error.get("violation", "Unknown schema violation"),
                    "fix": schema_error.get("fix", "Fix frontmatter to conform to schema")
                })

    return {
        "assert_count": check_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED"
    }
