"""
ASSERT_CC_INPUTS_SATISFIED_V0 - Handler

Enforces INVARIANT_CC_INPUTS_SATISFIED_V0 at compile time.

Validates JSONPath reference availability for all WF artifacts:
- All $.payload.* references exist in IN payload schema
- All $.results.step_name.* references point to earlier steps with valid outputs

Validation Scope: AVAILABILITY ONLY (not type safety, not schema conformance)

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate CC inputs satisfaction against pre-computed structural analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed cc_inputs_satisfied

    Returns:
        {
            "assert_count": int,
            "violations": list[dict],  # Standardized schema
            "status": "PASSED/FAILED"
        }
    """
    violations = []
    wf_count = 0

    # STRICT INVERSION OF CONTROL: Compiler must provide complete context
    cc_inputs_satisfied = compilation_context.get("cc_inputs_satisfied")

    if cc_inputs_satisfied is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "capability_contracts::ASSERT_CC_INPUTS_SATISFIED_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing cc_inputs_satisfied",
                "fix": "Compiler must pre-compute CC inputs satisfaction analysis before assert phase"
            }],
            "status": "FAILED"
        }

    # Validation is per-WF: the validator resolves CC input references within WF context
    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_count += 1
        fqdn = artifact["fqdn_id"]
        inputs_result = cc_inputs_satisfied.get(fqdn)

        if not inputs_result:
            violations.append({
                "fqdn": fqdn,
                "rule": "capability_contracts::INVARIANT_CC_INPUTS_SATISFIED_V0",
                "message": "Missing inputs satisfaction analysis for WF artifact",
                "fix": "Compiler must analyze all WF artifacts"
            })
            continue

        # Translate structural violations to standardized rule violations
        if inputs_result.get("status") in ("FAILED", "VIOLATION"):
            for structural_violation in inputs_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "capability_contracts::INVARIANT_CC_INPUTS_SATISFIED_V0",
                    "message": structural_violation.get("violation", "Unknown CC inputs violation"),
                    "fix": structural_violation.get("fix", "Ensure all CC inputs are satisfied")
                })

    # Return standardized result
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
