"""
ASSERT_TOPOLOGY_CAPABILITY_REFERENCE_UNIQUE_V0

Enforces INVARIANT_TOPOLOGY_CAPABILITY_REFERENCE_UNIQUE_V0 at compile time.

Validates that each execution topology step references exactly one capability —
exactly one of `transform` (CT) or `side_effect` (CS), not both, not neither.

Validation scope: structural capability reference uniqueness per step.
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

        for i, step in enumerate(pipeline):
            if not isinstance(step, dict):
                continue

            step_id = step.get("step") or i
            has_transform = "transform" in step
            has_side_effect = "side_effect" in step

            if has_transform and has_side_effect:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "capability_contracts::INVARIANT_TOPOLOGY_CAPABILITY_REFERENCE_UNIQUE_V0",
                    "message": (
                        f"Step '{step_id}' has both 'transform' and 'side_effect' — "
                        "exactly one capability reference is allowed per step"
                    ),
                    "fix": "Remove one of transform or side_effect; each step binds exactly one capability",
                })
            elif not has_transform and not has_side_effect:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "capability_contracts::INVARIANT_TOPOLOGY_CAPABILITY_REFERENCE_UNIQUE_V0",
                    "message": (
                        f"Step '{step_id}' has no capability reference — "
                        "exactly one of 'transform' or 'side_effect' is required"
                    ),
                    "fix": "Add 'transform: <CT_FQDN>' or 'side_effect: <CS_FQDN>' to this step",
                })

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
