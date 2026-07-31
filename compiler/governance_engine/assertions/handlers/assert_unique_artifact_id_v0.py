"""
ASSERT_UNIQUE_ARTIFACT_ID_V0 Handler

Validates each fqdn_id appears exactly once in compilation graph.
"""

from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify each fqdn_id is unique.

    Args:
        artifacts: All discovered artifacts (raw list before dict conversion)
        compilation_context: Not used

    Returns:
        {
            "assert_count": int,
            "violations": list[dict]
        }
    """
    violations = []
    seen = {}

    for artifact in artifacts:
        fqdn = artifact.get("fqdn_id")
        if not fqdn:
            continue

        if fqdn in seen:
            seen[fqdn] += 1
        else:
            seen[fqdn] = 1

    # Report duplicates
    for fqdn, count in seen.items():
        if count > 1:
            violations.append({
                "fqdn": fqdn,
                "rule": "fb.artifact::INVARIANT_UNIQUE_ARTIFACT_ID_V0",
                "message": f"Duplicate fqdn_id (appears {count} times in compilation graph)",
                "fix": "Ensure each artifact has a unique FQDN (layer::artifact_code combination)"
            })

    if violations:
        return {
            "assert_count": len(seen),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(seen),
        "violations": [],
        "status": "PASSED"
    }
