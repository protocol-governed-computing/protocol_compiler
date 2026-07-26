"""
ASSERT_COMPILER_NO_EXECUTION_V0 Handler

Verifies compiled CT and CS artifacts do not carry execution-time state fields
in their materialized frontmatter.

Execution-state fields are fields that would only be present in an artifact's
frontmatter if the compiler invoked the artifact's implementation during compilation.
Their presence is a constitutional violation.
"""

from typing import Any

# Fields that indicate execution-time state contamination in compiled artifact frontmatter.
# These fields are only produced by executing an artifact, not by declaring one.
_EXECUTION_STATE_FIELDS = frozenset({
    "trace_id",
    "execution_result",
    "runtime_output",
    "invocation_id",
    "execution_state",
    "runtime_state",
})


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify CT and CS artifact frontmatter contains no execution-time state fields.

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
    checked = 0

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type not in ("CT", "CS"):
            continue

        checked += 1
        fqdn_id = artifact.get("fqdn_id", "<unknown>")
        artifact_code = artifact.get("artifact_code", "<unknown>")
        frontmatter = artifact.get("frontmatter", {})

        # Check top-level frontmatter keys for execution-state fields
        contaminated_fields = _EXECUTION_STATE_FIELDS & set(frontmatter.keys())

        if contaminated_fields:
            violations.append({
                "fqdn": fqdn_id,
                "artifact_code": artifact_code,
                "artifact_type": artifact_type,
                "contaminated_fields": sorted(contaminated_fields),
                "rule": "fb.constitution::INVARIANT_COMPILER_NO_EXECUTION_V0",
                "message": (
                    f"{artifact_type} artifact frontmatter contains execution-state fields: "
                    f"{sorted(contaminated_fields)}"
                ),
                "fix": (
                    "Remove execution-state fields from the artifact declaration. "
                    "Compiled CT/CS artifacts must be pure declarations — "
                    "execution outputs must not appear in compiled frontmatter."
                ),
            })

    if violations:
        return {
            "assert_count": checked,
            "violations": violations,
            "status": "FAILED",
        }

    return {
        "assert_count": checked,
        "violations": [],
        "status": "PASSED",
    }
