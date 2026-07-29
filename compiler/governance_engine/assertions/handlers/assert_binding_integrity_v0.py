"""
ASSERT_BINDING_INTEGRITY_V0 Handler

Validates RB binding integrity:
1. All binding keys must be FQDNs (contain '::')
2. All binding keys must reference artifacts that exist in the compiled graph

CONSTITUTIONAL: Binding surfaces must be structurally sound at compile time.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate RB binding integrity via pre-computed analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed rb_binding_integrity

    Returns:
        Standardized result dict with assert_count, violations, status
    """
    violations = []
    rb_count = 0

    rb_integrity = compilation_context.get("rb_binding_integrity")

    if rb_integrity is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "fb.runtime_binding::ASSERT_BINDING_INTEGRITY_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing rb_binding_integrity",
                "fix": "Compiler must pre-compute RB binding analysis before assert phase"
            }],
            "status": "FAILED"
        }

    for artifact in artifacts:
        if artifact.get("artifact_type") != "RB":
            continue

        rb_count += 1
        fqdn = artifact["fqdn_id"]
        result = rb_integrity.get(fqdn)

        if not result:
            continue

        if result.get("status") == "FAILED":
            for structural_violation in result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "fb.runtime_binding::INVARIANT_BINDING_INTEGRITY_V0",
                    "message": structural_violation.get("violation", "Unknown RB binding violation"),
                    "fix": structural_violation.get("fix", "Fix RB binding reference")
                })

    return {
        "assert_count": rb_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED"
    }
