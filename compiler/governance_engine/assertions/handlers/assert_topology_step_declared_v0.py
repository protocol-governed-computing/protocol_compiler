"""
ASSERT_TOPOLOGY_STEP_DECLARED_V0

Enforces INVARIANT_TOPOLOGY_STEP_DECLARED_V0 at compile time.

Validates that every execution topology step in a CC pipeline is an explicit
typed dict with a declared `step` field. Detects wildcard $.results.* input
references that bypass step-identity addressing.

Validation scope: structural declaration completeness only.
Execution topology validation is structural, not semantic.
"""

import re

# Wildcard: $.results.* without a step ID (e.g., $.results.*.field or $.results.field)
_WILDCARD_RESULTS_PATTERN = re.compile(r"^\$\.results\.\*")


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
            # Each step must be a typed dict — not a string, not a scalar
            if not isinstance(step, dict):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.invariants::INVARIANT_TOPOLOGY_STEP_DECLARED_V0",
                    "message": f"Pipeline step at index {i} is {type(step).__name__}, not a typed step dict",
                    "fix": "Replace string pipeline entries with explicit typed step objects",
                })
                continue

            step_id = step.get("step")

            # Each step must have an explicit 'step' field
            if not step_id:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.invariants::INVARIANT_TOPOLOGY_STEP_DECLARED_V0",
                    "message": f"Pipeline step at index {i} missing explicit 'step' identifier",
                    "fix": "Add a unique 'step' field to every pipeline step",
                })

            # Detect wildcard $.results.* input references (bypass of step identity)
            inputs = step.get("inputs", {})
            if isinstance(inputs, dict):
                for input_name, ref in inputs.items():
                    if isinstance(ref, str) and _WILDCARD_RESULTS_PATTERN.match(ref):
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "governance.invariants::INVARIANT_TOPOLOGY_STEP_DECLARED_V0",
                            "message": (
                                f"Step '{step_id or i}' input '{input_name}' uses wildcard reference "
                                f"'{ref}' — must reference a specific declared step ID"
                            ),
                            "fix": "Replace $.results.*.field with $.results.<step_id>.field",
                        })

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
