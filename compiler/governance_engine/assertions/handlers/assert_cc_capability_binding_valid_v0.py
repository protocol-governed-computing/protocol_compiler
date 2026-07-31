"""
ASSERT_CC_CAPABILITY_BINDING_VALID_V0 Handler

Validates CC pipeline step capability bindings:
- Each step must bind exactly ONE capability (CT or CS, not both, not zero)
- Referenced capabilities must exist in compilation graph

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all CC capability bindings against pre-computed structural analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed cc_bindings

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
    cc_bindings = compilation_context.get("cc_bindings")

    if cc_bindings is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "fb.capability_contracts::ASSERT_CC_CAPABILITY_BINDING_VALID_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing cc_bindings",
                "fix": "Compiler must pre-compute CC binding analysis before assert phase"
            }],
            "status": "FAILED"
        }

    # Check rules against pre-computed structure
    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue

        cc_count += 1
        fqdn = artifact["fqdn_id"]
        binding_result = cc_bindings.get(fqdn)

        if not binding_result:
            violations.append({
                "fqdn": fqdn,
                "rule": "fb.capability_contracts::INVARIANT_CC_CAPABILITY_BINDING_VALID_V0",
                "message": "Missing capability binding analysis for CC artifact",
                "fix": "Compiler must analyze all CC artifacts"
            })
            continue

        # Translate structural violations to standardized rule violations
        if binding_result.get("status") == "FAILED":
            for structural_violation in binding_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "fb.capability_contracts::INVARIANT_CC_CAPABILITY_BINDING_VALID_V0",
                    "message": structural_violation.get("violation", "Unknown CC binding violation"),
                    "fix": structural_violation.get("fix", "Fix CC capability binding")
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
