"""
ASSERT_WF_CC_ONLY_NODES_V0 Handler

Validates that all non-structural WF nodes are of type CC.
Structural node types IN and EXIT are permitted.
Direct CT or CS node references in a workflow are forbidden.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

STRUCTURAL_TYPES = {"IN", "EXIT"}
PERMITTED_TYPES = {"CC", "IN", "EXIT"}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate all WF node types against CC-only constraint.

    Args:
        artifacts: All validated artifacts
        compilation_context: Compilation context (unused; all data from artifacts)

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    wf_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_code = artifact.get("artifact_code", "UNKNOWN")
        wf_count += 1

        nodes = artifact.get("frontmatter", {}).get("core", {}).get("nodes", {})
        for node_name, node_def in nodes.items():
            node_type = node_def.get("type")
            if node_type not in PERMITTED_TYPES:
                violations.append({
                    "assert": "ASSERT_WF_CC_ONLY_NODES_V0",
                    "artifact": wf_code,
                    "node": node_name,
                    "node_type": node_type,
                    "violation": (
                        f"Workflow node must be CC, IN, or EXIT; "
                        f"found type '{node_type}'"
                    ),
                    "fix": "Move CT/CS invocations inside a CC artifact",
                })

    return {
        "assert_count": wf_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
