"""
ASSERT_WF_ENTRY_INTENT_V0 Handler

Validates that every WF declares exactly one IN node as its entry intent
and that start_node references it.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate every WF has exactly one IN entry intent.

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

        core = artifact.get("frontmatter", {}).get("core", {})
        nodes = core.get("nodes", {})

        in_nodes = [
            name for name, defn in nodes.items()
            if defn.get("type") == "IN"
        ]

        if len(in_nodes) == 0:
            violations.append({
                "assert": "ASSERT_WF_ENTRY_INTENT_V0",
                "artifact": wf_code,
                "in_nodes": in_nodes,
                "violation": "Workflow must declare exactly one IN node; found none",
                "fix": "Add an IN node and set start_node to reference it",
            })
        elif len(in_nodes) > 1:
            violations.append({
                "assert": "ASSERT_WF_ENTRY_INTENT_V0",
                "artifact": wf_code,
                "in_nodes": in_nodes,
                "violation": (
                    f"Workflow must declare exactly one IN node; "
                    f"found {len(in_nodes)}: {in_nodes}"
                ),
                "fix": "Consolidate into a single IN node",
            })

    return {
        "assert_count": wf_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
