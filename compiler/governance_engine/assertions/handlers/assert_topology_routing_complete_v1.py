"""
ASSERT_TOPOLOGY_ROUTING_COMPLETE_V1

Enforces INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V1 at compile time.

Validates that every execution topology step's on_result covers exactly the
set of status codes declared in that step's result_surface. Unrouted surface
codes are ungoverned execution paths. Unknown codes in on_result (not in
result_surface) are governance noise.

Validation is step-local: each step's on_result is validated against that
step's own result_surface, NOT against the CC-level result_status_contract.allowed.
CC-level contract closure is enforced by ASSERT_TOPOLOGY_CONTRACT_CLOSED_V1.

A step's result_surface is the author's statement, and it cannot narrow what the capability it
dispatches declares (`3d` CP-13). So the surface must also hold every outcome the capability
declares: a side effect's operation declares its `result_status_values`; a transform declares
SUCCESS, and VIOLATION unless its `refusal` is `never`. A capability this build cannot see is left
to the reference checks, which refuse it.

A stood-down contract is not checked: it is present and not in force
(`artifact::INVARIANT_SUPERSEDED_NOT_IN_FORCE_V0`), and its successor is.

Validation scope: step routing completeness against declared step result surface.
Execution topology validation is structural, not semantic.
"""

from compiler.atoms.force import in_force


def _declared(step: dict, compilation_context: dict) -> set[str] | None:
    """The outcomes the capability a step dispatches declares, or None if it is not visible."""
    local = compilation_context.get("artifacts_by_fqdn", {}) or {}
    imported = compilation_context.get("imported_frontmatter", {}) or {}

    def frontmatter(fqdn: str) -> dict | None:
        if fqdn in local:
            return local[fqdn].get("frontmatter", {}) or {}
        return imported.get(fqdn)

    if step.get("side_effect"):
        fm = frontmatter(step["side_effect"])
        if fm is None:
            return None
        operation = ((fm.get("core", {}) or {}).get("operations", {}) or {}).get(step.get("op"))
        if not isinstance(operation, dict):
            return None
        return set(operation.get("result_status_values", []) or [])
    if step.get("transform"):
        fm = frontmatter(step["transform"])
        if fm is None:
            return None
        refusal = (fm.get("core", {}) or {}).get("refusal")
        return {"SUCCESS"} if refusal == "never" else {"SUCCESS", "VIOLATION"}
    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    cc_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "CC":
            continue
        if not in_force(artifact.get("frontmatter", {}) or {}):
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

            # Narrowed: declared by the dispatched capability but absent from the surface (CP-13)
            declared = _declared(step, compilation_context)
            for code in sorted((declared or set()) - surface):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "execution_topology::INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V1",
                    "message": (
                        f"Step '{step_id}' result_surface omits '{code}', which "
                        f"{step.get('side_effect') or step.get('transform')} declares — a surface "
                        f"cannot narrow what the dispatched capability can answer (3d CP-13)"
                    ),
                    "fix": f"Add '{code}' to step '{step_id}' result_surface and route it in on_result",
                })

            # Unrouted: declared in result_surface but absent from on_result
            unrouted = surface - routed_codes
            for code in sorted(unrouted):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "execution_topology::INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V1",
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
                    "rule": "execution_topology::INVARIANT_TOPOLOGY_ROUTING_COMPLETE_V1",
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
