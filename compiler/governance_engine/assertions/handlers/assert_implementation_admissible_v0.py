"""
ASSERT_IMPLEMENTATION_ADMISSIBLE_V0 Handler

Validates implementation admissibility for capability artifacts:
1. CT atoms must have machine.implementation with non-empty module and callable
2. CS artifacts must have implementation with non-empty module and callable
3. CT molecules are exempt (they compose atoms via atom_stream)

CONSTITUTIONAL: Implementation admissibility is a compile-time invariant.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate implementation admissibility via pre-computed analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed implementation_admissibility

    Returns:
        Standardized result dict with assert_count, violations, status
    """
    violations = []
    check_count = 0

    admissibility = compilation_context.get("implementation_admissibility")

    if admissibility is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "execution::ASSERT_IMPLEMENTATION_ADMISSIBLE_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing implementation_admissibility",
                "fix": "Compiler must pre-compute implementation admissibility analysis before assert phase"
            }],
            "status": "FAILED"
        }

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in ("CT", "CS"):
            continue

        check_count += 1
        fqdn = artifact["fqdn_id"]
        result = admissibility.get(fqdn)

        if not result:
            continue

        if result.get("status") == "FAILED":
            for structural_violation in result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "execution::INVARIANT_IMPLEMENTATION_ADMISSIBLE_V0",
                    "message": structural_violation.get("violation", "Unknown implementation violation"),
                    "fix": structural_violation.get("fix", "Fix implementation declaration")
                })

    return {
        "assert_count": check_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED"
    }
