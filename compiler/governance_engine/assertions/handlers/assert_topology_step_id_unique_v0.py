"""
ASSERT_TOPOLOGY_STEP_ID_UNIQUE_V0

Enforces INVARIANT_TOPOLOGY_STEP_ID_UNIQUE_V0 at compile time.

Validates that step IDs are unique within each CC execution topology pipeline.
Duplicate step IDs create ambiguous dataflow identity — downstream steps
referencing $.results.<step_id>.* cannot resolve deterministically.

Validation scope: step identity uniqueness within pipeline scope.
Execution topology validation is structural, not semantic.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    cc_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue

        cc_count += 1
        fqdn = artifact.get("fqdn_id", "unknown")
        core = artifact.get("frontmatter", {}).get("core", {})
        pipeline = core.get("pipeline", [])

        if not isinstance(pipeline, list):
            continue

        seen_ids: set[str] = set()
        duplicate_ids: set[str] = set()

        for step in pipeline:
            if not isinstance(step, dict):
                continue
            step_id = step.get("step")
            if not isinstance(step_id, str):
                continue
            if step_id in seen_ids:
                duplicate_ids.add(step_id)
            else:
                seen_ids.add(step_id)

        for dup_id in sorted(duplicate_ids):
            violations.append({
                "fqdn": fqdn,
                "rule": "fb.execution_topology::INVARIANT_TOPOLOGY_STEP_ID_UNIQUE_V0",
                "message": (
                    f"Duplicate step ID '{dup_id}' detected in pipeline — "
                    "step IDs must be unique within a CC execution topology"
                ),
                "fix": "Assign a unique 'step' identifier to each pipeline step",
            })

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
