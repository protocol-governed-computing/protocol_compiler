"""
ASSERT_TOPOLOGY_ROUTING_COMPLETE_V0

Enforces INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V0 at compile time.

Validates that every execution topology step's on_result covers exactly the
set of status codes declared in that step's result_surface. Unrouted surface
codes are ungoverned execution paths. Unknown codes in on_result (not in
result_surface) are governance noise.

Validation is step-local: each step's on_result is validated against that
step's own result_surface, NOT against the CC-level result_status_contract.allowed.
CC-level contract closure is enforced by ASSERT_TOPOLOGY_CONTRACT_CLOSED_V0.

Validation scope: step routing completeness against declared step result surface.
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

        for step in pipeline:
            if not isinstance(step, dict):
                continue

            step_id = step.get("step") or "unknown"
            on_result = step.get("on_result")

            if not isinstance(on_result, dict):
                continue

            surface = set(step.get("result_surface", []))
            routed_codes = set(on_result.keys())

            # Unrouted: declared in result_surface but absent from on_result
            unrouted = surface - routed_codes
            for code in sorted(unrouted):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.invariants::INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V0",
                    "message": (
                        f"Step '{step_id}' on_result missing routing for surface code '{code}' "
                        f"— declared in step result_surface but has no routing entry"
                    ),
                    "fix": f"Add '{code}: continue | exit' to step '{step_id}' on_result",
                })

            # Unknown: present in on_result but not in result_surface (governance noise)
            unknown = routed_codes - surface
            for code in sorted(unknown):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.invariants::INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V0",
                    "message": (
                        f"Step '{step_id}' on_result contains code '{code}' "
                        f"— not declared in step result_surface"
                    ),
                    "fix": (
                        f"Remove '{code}' from step '{step_id}' on_result, "
                        "or add it to that step's result_surface if this capability can produce it"
                    ),
                })

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
