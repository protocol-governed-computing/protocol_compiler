"""
ASSERT_ARTIFACT_CONTENT_HASH_DECLARED_V0 Handler

Verifies every compiled artifact in the snapshot carries a non-empty content_hash —
confirming full materialization of the compiled set.
"""

from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify every compiled artifact has a non-empty content_hash.

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

    for artifact in artifacts:
        fqdn_id = artifact.get("fqdn_id", "<unknown>")
        artifact_code = artifact.get("artifact_code", "<unknown>")
        content_hash = artifact.get("content_hash")

        if not content_hash:
            violations.append({
                "fqdn": fqdn_id,
                "artifact_code": artifact_code,
                "content_hash": content_hash,
                "rule": "fb.compiler::INVARIANT_ARTIFACT_CONTENT_HASH_DECLARED_V0",
                "message": (
                    f"Artifact is not fully materialized: content_hash is "
                    f"{'missing' if content_hash is None else 'empty'}"
                ),
                "fix": (
                    "Ensure the MATERIALIZE phase computes and assigns content_hash "
                    "for every compiled artifact before emitting the snapshot."
                ),
            })

    if violations:
        return {
            "assert_count": len(artifacts),
            "violations": violations,
            "status": "FAILED",
        }

    return {
        "assert_count": len(artifacts),
        "violations": [],
        "status": "PASSED",
    }
