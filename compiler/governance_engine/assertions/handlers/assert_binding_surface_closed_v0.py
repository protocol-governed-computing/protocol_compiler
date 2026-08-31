"""
ASSERT_BINDING_SURFACE_CLOSED_V0 - Handler

Enforces INVARIANT_BINDING_SURFACE_CLOSED_V0 at compile time.

Validates WF-level binding surface for all WF artifacts:
- All $.payload.<field> bindings reference declared IN payload schema fields
- All $.results.<NODE>.<field> bindings reference an existing WF CC node
  with that field declared in the CC's core.outputs
- No unrecognized binding grammar (any other $ prefix)

CONSTITUTIONAL: Pure rule checker — reads pre-computed wf_binding_surface from context.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Assert WF binding surface is closed against pre-computed structural analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed wf_binding_surface

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],
            "status": "PASSED/FAILED"
        }
    """
    wf_binding_surface = compilation_context.get("wf_binding_surface")

    if wf_binding_surface is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "runtime_binding::ASSERT_BINDING_SURFACE_CLOSED_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing wf_binding_surface",
                "fix": (
                    "Compiler must pre-compute WF binding surface analysis "
                    "before assert phase"
                )
            }],
            "status": "FAILED"
        }

    violations = []
    wf_count = 0

    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_count += 1
        fqdn = artifact["fqdn_id"]
        surface_result = wf_binding_surface.get(fqdn)

        if not surface_result:
            violations.append({
                "fqdn": fqdn,
                "rule": "runtime_binding::INVARIANT_BINDING_SURFACE_CLOSED_V0",
                "message": "Missing binding surface analysis for WF artifact",
                "fix": "Compiler must analyze all WF artifacts for binding surface"
            })
            continue

        if surface_result.get("status") == "VIOLATION":
            for structural_violation in surface_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "runtime_binding::INVARIANT_BINDING_SURFACE_CLOSED_V0",
                    "message": structural_violation.get(
                        "violation", "Unknown binding surface violation"
                    ),
                    "fix": structural_violation.get(
                        "fix", "Correct the binding reference"
                    )
                })

    if violations:
        return {
            "assert_count": wf_count,
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": wf_count,
        "violations": [],
        "status": "PASSED"
    }
