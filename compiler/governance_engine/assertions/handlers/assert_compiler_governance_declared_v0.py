"""
ASSERT_COMPILER_GOVERNANCE_DECLARED_V0 Handler

Verifies CONSTITUTION_COMPILER_V0 is present in the compiled artifact set
and declares a non-empty rules list — enforcing COMPILER_SELF_APPLICABLE.
"""

from typing import Any

_COMPILER_CONSTITUTION_FQDN = "fb.constitution::CONSTITUTION_COMPILER_V0"


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
            "rule": "fb.constitution::INVARIANT_COMPILER_GOVERNANCE_DECLARED_V0",
            "message": (
                f"COMPILER_SELF_APPLICABLE violated: {_COMPILER_CONSTITUTION_FQDN} "
                "is absent from the compiled artifact set"
            ),
            "fix": (
                "Ensure the STRUCTURE declaration includes fb.constitution as a "
                "governed boundary so CONSTITUTION_COMPILER_V0 is discovered and compiled"
            ),
        })
    else:
        frontmatter = constitution.get("frontmatter", {})
        rules = frontmatter.get("rules", [])

        if not rules:
            violations.append({
                "fqdn": _COMPILER_CONSTITUTION_FQDN,
                "rule": "fb.constitution::INVARIANT_COMPILER_GOVERNANCE_DECLARED_V0",
                "message": (
                    f"{_COMPILER_CONSTITUTION_FQDN} machine block has no declared rules — "
                    "governance declaration surface is empty"
                ),
                "fix": "Restore the rules list in CONSTITUTION_COMPILER_V0 machine block",
            })

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
