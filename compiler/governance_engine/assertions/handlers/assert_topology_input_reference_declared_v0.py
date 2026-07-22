"""
ASSERT_TOPOLOGY_INPUT_REFERENCE_DECLARED_V0

Enforces INVARIANT_TOPOLOGY_INPUT_REFERENCE_DECLARED_V0 at compile time.

Validates that all $.results.<step_id>.* input references in execution topology
steps resolve to a step ID declared earlier in the same pipeline. Detects:
- Dangling references (step_id not declared in the pipeline at all)
- Forward references (step_id declared later in the pipeline — result not yet available)

$.inputs.* references are always valid — they resolve to CC-level inputs.

Validation scope: dataflow closure — all input references must resolve to
declared prior steps. Execution topology validation is structural, not semantic.
"""

import re

# Matches $.results.<step_id>.anything — captures step_id
_RESULTS_REF_PATTERN = re.compile(r"^\$\.results\.([^.]+)\.")


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

        # Build ordered list of declared step IDs for forward-reference detection
        all_step_ids: list[str] = []
        for step in pipeline:
            if isinstance(step, dict):
                sid = step.get("step")
                if isinstance(sid, str):
                    all_step_ids.append(sid)

        declared_step_ids: set[str] = set(all_step_ids)

        # Walk steps in order; track which step IDs have been declared so far
        prior_step_ids: set[str] = set()

        for step in pipeline:
            if not isinstance(step, dict):
                continue

            step_id = step.get("step")
            if isinstance(step_id, str):
                current_step_label = step_id
            else:
                current_step_label = "unknown"

            inputs = step.get("inputs", {})
            if isinstance(inputs, dict):
                for input_name, ref in inputs.items():
                    if not isinstance(ref, str):
                        continue

                    m = _RESULTS_REF_PATTERN.match(ref)
                    if not m:
                        continue  # $.inputs.* or other non-results reference — not checked here

                    referenced_step_id = m.group(1)

                    if referenced_step_id not in declared_step_ids:
                        # Dangling reference — step_id doesn't exist in this pipeline
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "governance.invariants::INVARIANT_TOPOLOGY_INPUT_REFERENCE_DECLARED_V0",
                            "message": (
                                f"Step '{current_step_label}' input '{input_name}' references "
                                f"undeclared step ID '{referenced_step_id}' — not found in pipeline"
                            ),
                            "fix": (
                                f"Declare a step with id '{referenced_step_id}' in the pipeline, "
                                "or correct the reference to an existing step ID"
                            ),
                        })
                    elif referenced_step_id not in prior_step_ids:
                        # Forward reference — step_id is declared but not yet executed
                        violations.append({
                            "fqdn": fqdn,
                            "rule": "governance.invariants::INVARIANT_TOPOLOGY_INPUT_REFERENCE_DECLARED_V0",
                            "message": (
                                f"Step '{current_step_label}' input '{input_name}' contains forward "
                                f"reference to step '{referenced_step_id}' — result not yet available "
                                f"at this point in the pipeline"
                            ),
                            "fix": (
                                f"Move step '{referenced_step_id}' before '{current_step_label}', "
                                "or restructure input bindings to reference only prior steps"
                            ),
                        })

            # After processing this step's inputs, add its ID to the prior set
            if isinstance(step_id, str):
                prior_step_ids.add(step_id)

    return {
        "assert_count": cc_count,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
