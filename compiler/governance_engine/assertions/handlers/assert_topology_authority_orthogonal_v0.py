"""
ASSERT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0

Enforces INVARIANT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0 at compile time.

Detects authority-semantic field names inside CC execution topology steps.
Authority evaluation is pre-execution and lives in the authority governance plane.
Topology must not encode authority semantics — no role branching, permission routing,
actor-dependent topology, or authorization field names inside steps.

Checked field positions per step: top-level step fields, inputs keys, outputs keys.

Validation scope: structural orthogonality — authority semantics must not
appear in topology step fields.
Execution topology validation is structural, not semantic.
"""

# Authority-semantic field names that must not appear inside topology steps.
# From INVARIANT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0 enforcement spec.
_AUTHORITY_FIELD_NAMES: frozenset[str] = frozenset({
    "role",
    "permissions",
    "authorized_by",
    "on_role",
    "required_role",
    "authorization",
    "execution_rights",
    "actor_type_gate",
    "permission_check",
})


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

            # Check top-level step fields
            for field_name in step:
                if field_name in _AUTHORITY_FIELD_NAMES:
                    violations.append({
                        "fqdn": fqdn,
                        "rule": "execution_topology::INVARIANT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0",
                        "message": (
                            f"Step '{step_id}' contains authority-semantic field '{field_name}' "
                            "— authority semantics must not appear in execution topology steps"
                        ),
                        "fix": (
                            f"Remove '{field_name}' from step '{step_id}'; "
                            "authority evaluation belongs in the authority governance plane, not topology"
                        ),
                    })

            # Check input binding keys
            inputs = step.get("inputs", {})
            if isinstance(inputs, dict):
                for key in inputs:
                    if key in _AUTHORITY_FIELD_NAMES:
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "execution_topology::INVARIANT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0",
                            "message": (
                                f"Step '{step_id}' input key '{key}' is an authority-semantic field name "
                                "— authority semantics must not appear in topology step inputs"
                            ),
                            "fix": (
                                f"Rename input '{key}' in step '{step_id}' to a topology-neutral name, "
                                "or restructure so authority data does not flow through topology inputs"
                            ),
                        })

            # Check output binding keys
            outputs = step.get("outputs", {})
            if isinstance(outputs, dict):
                for key in outputs:
                    if key in _AUTHORITY_FIELD_NAMES:
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "execution_topology::INVARIANT_TOPOLOGY_AUTHORITY_ORTHOGONAL_V0",
                            "message": (
                                f"Step '{step_id}' output key '{key}' is an authority-semantic field name "
                                "— authority semantics must not appear in topology step outputs"
                            ),
                            "fix": (
                                f"Rename output '{key}' in step '{step_id}' to a topology-neutral name"
                            ),
                        })

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
