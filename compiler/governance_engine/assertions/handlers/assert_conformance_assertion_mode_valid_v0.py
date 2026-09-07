"""
ASSERT_CONFORMANCE_ASSERTION_MODE_VALID_V0 Handler

Parity stub for INVARIANT_CONFORMANCE_ASSERTION_MODE_VALID_V0.

The closed-vocabulary enforcement (mode ∈ {exact, property, schema}, type constraints)
is fully implemented in the VALIDATE_TEST_DATA compiler phase. This handler exists to
satisfy the 1:1 INVARIANT/ASSERT parity invariant enforced by ASSERT_ASSERT_PARITY_V0.

CONSTITUTIONAL: Pure rule checker — no side effects
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Parity stub — enforcement delegated to VALIDATE_TEST_DATA phase.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED"
        }
    """
    td_count = sum(1 for a in artifacts if a.get("artifact_type") == "TEST_DATA")

    return {
        "assert_count": td_count,
        "violations": [],
        "status": "PASSED",
    }
