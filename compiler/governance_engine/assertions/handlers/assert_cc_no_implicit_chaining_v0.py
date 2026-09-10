"""
ASSERT_CC_NO_IMPLICIT_CHAINING_V0 Handler

Validates CC artifacts contain no orchestration logic:
- No next_step field (explicit chaining)
- No next field (state transitions)
- No transitions field (workflow logic)
- No flow field (control flow)
- No conditional field (branching)
- No loop field (iteration)

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all CC artifacts for absence of orchestration logic against pre-computed analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed cc_chaining

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],  # Standardized schema
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    cc_count = 0

    # STRICT INVERSION OF CONTROL: Compiler must provide complete context
    cc_chaining = compilation_context.get("cc_chaining")

    if cc_chaining is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "capability_contracts::ASSERT_CC_NO_IMPLICIT_CHAINING_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing cc_chaining",
                "fix": "Compiler must pre-compute CC chaining analysis before assert phase"
            }],
            "status": "FAILED"
        }

    # Check rules against pre-computed structure
    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue

        cc_count += 1
        fqdn = artifact["fqdn_id"]
        chaining_result = cc_chaining.get(fqdn)

        if not chaining_result:
            violations.append({
                "fqdn": fqdn,
                "rule": "capability_contracts::INVARIANT_CC_NO_IMPLICIT_CHAINING_V0",
                "message": "Missing chaining analysis for CC artifact",
                "fix": "Compiler must analyze all CC artifacts"
            })
            continue

        # Translate structural violations to standardized rule violations
        if chaining_result.get("status") == "FAILED":
            for structural_violation in chaining_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "capability_contracts::INVARIANT_CC_NO_IMPLICIT_CHAINING_V0",
                    "message": structural_violation.get("violation", "Unknown CC chaining violation"),
                    "fix": structural_violation.get("fix", "Remove orchestration fields from CC")
                })

    # Return standardized result
    if violations:
        return {
            "assert_count": cc_count,
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": cc_count,
        "violations": [],
        "status": "PASSED"
    }
