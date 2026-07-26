"""
ASSERT_CC_STORAGE_OP_CONFORMANCE_V0 Handler

Validates that every CC pipeline step with a side_effect binding declares an op
that exists in the target CS's core.policy.operations list.

CONSTITUTIONAL: Pure rule checker — reads pre-computed structure from context.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all CC op declarations against pre-computed CS operation conformance.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed cc_op_conformance

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    cc_count = 0

    cc_op_conformance = compilation_context.get("cc_op_conformance")

    if cc_op_conformance is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "governance.layers::ASSERT_CC_STORAGE_OP_CONFORMANCE_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing cc_op_conformance",
                "fix": "Compiler must pre-compute CC op conformance analysis before assert phase"
            }],
            "status": "FAILED"
        }

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue

        cc_count += 1
        fqdn = artifact["fqdn_id"]
        conformance_result = cc_op_conformance.get(fqdn)

        if not conformance_result:
            continue  # CC has no CS-binding steps — exempt

        if conformance_result.get("status") == "FAILED":
            for structural_violation in conformance_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "fb.topology::INVARIANT_CC_STORAGE_OP_CONFORMANCE_V0",
                    "message": structural_violation.get("violation", "Unknown op conformance violation"),
                    "fix": structural_violation.get("fix", "Correct op to match CS declared operations"),
                })

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
