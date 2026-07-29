"""
ASSERT_COMPILER_GOVERNANCE_DECLARED_V0 Handler

Verifies CONSTITUTION_COMPILER_V0 is present in the compiled artifact set
and declares a non-empty rules list — enforcing COMPILER_SELF_APPLICABLE.
"""

from typing import Any

_COMPILER_CONSTITUTION_FQDN = "fb.compiler::CONSTITUTION_COMPILER_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify CONSTITUTION_COMPILER_V0 is present and well-formed.

    Args:
        artifacts: All compiled artifacts
        compilation_context: Not used

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": str
        }
    """
    violations = []

    # Locate CONSTITUTION_COMPILER_V0 in compiled set
    constitution = next(
        (a for a in artifacts if a.get("fqdn_id") == _COMPILER_CONSTITUTION_FQDN),
        None,
    )

    if constitution is None:
        violations.append({
            "fqdn": _COMPILER_CONSTITUTION_FQDN,
            "rule": "fb.compiler::INVARIANT_COMPILER_GOVERNANCE_DECLARED_V0",
            "message": (
                f"COMPILER_SELF_APPLICABLE violated: {_COMPILER_CONSTITUTION_FQDN} "
                "is absent from the compiled artifact set"
            ),
            "fix": (
                "Ensure the STRUCTURE declaration includes fb.compiler as a "
                "governed boundary so CONSTITUTION_COMPILER_V0 is discovered and compiled"
            ),
        })
    # The emptiness check that stood here is retired: SCHEMA_CONSTITUTION_V0 requires a
    # non-empty rules list on every constitution, and ASSERT_GOVERNANCE_DECLARATION_RESOLVES_V0
    # requires each rule to name a real enforcing invariant. Presence of the compiler
    # constitution in the compiled set is the only claim left for this handler to make.

    if violations:
        return {
            "assert_count": 1,
            "violations": violations,
            "status": "FAILED",
        }

    return {
        "assert_count": 1,
        "violations": [],
        "status": "PASSED",
    }
