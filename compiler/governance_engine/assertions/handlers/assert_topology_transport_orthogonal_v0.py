"""
ASSERT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0

Enforces INVARIANT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0 at compile time.

Detects transport-semantic field names inside CC execution topology steps.
Transport governs execution boundaries (TI/TE). Topology governs traversal.
These are orthogonal governance planes and must not bleed into each other.
No HTTP routing, endpoint dispatch, transport conditions, or TE projection
rules may appear inside topology steps.

Checked field positions per step: top-level step fields, inputs keys, outputs keys.

Validation scope: structural orthogonality — transport semantics must not
appear in topology step fields.
Execution topology validation is structural, not semantic.
"""

# Transport-semantic field names that must not appear inside topology steps.
# From INVARIANT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0 enforcement spec.
_TRANSPORT_FIELD_NAMES: frozenset[str] = frozenset({
    "http_method",
    "endpoint",
    "transport_target",
    "url",
    "route",
    "response_code",
    "status_code",
    "content_type",
    "headers",
    "projection_rules",
    "visibility",
    "te_binding",
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
                if field_name in _TRANSPORT_FIELD_NAMES:
                    violations.append({
                        "fqdn": fqdn,
                        "rule": "governance.invariants::INVARIANT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0",
                        "message": (
                            f"Step '{step_id}' contains transport-semantic field '{field_name}' "
                            "— transport semantics must not appear in execution topology steps"
                        ),
                        "fix": (
                            f"Remove '{field_name}' from step '{step_id}'; "
                            "transport semantics belong in the transport governance plane, not topology"
                        ),
                    })

            # Check input binding keys
            inputs = step.get("inputs", {})
            if isinstance(inputs, dict):
                for key in inputs:
                    if key in _TRANSPORT_FIELD_NAMES:
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "governance.invariants::INVARIANT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0",
                            "message": (
                                f"Step '{step_id}' input key '{key}' is a transport-semantic field name "
                                "— transport semantics must not appear in topology step inputs"
                            ),
                            "fix": (
                                f"Rename input '{key}' in step '{step_id}' to a topology-neutral name"
                            ),
                        })

            # Check output binding keys
            outputs = step.get("outputs", {})
            if isinstance(outputs, dict):
                for key in outputs:
                    if key in _TRANSPORT_FIELD_NAMES:
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "governance.invariants::INVARIANT_TOPOLOGY_TRANSPORT_ORTHOGONAL_V0",
                            "message": (
                                f"Step '{step_id}' output key '{key}' is a transport-semantic field name "
                                "— transport semantics must not appear in topology step outputs"
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
