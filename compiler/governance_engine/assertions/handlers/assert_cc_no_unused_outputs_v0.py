"""
ASSERT_CC_NO_UNUSED_OUTPUTS_V0 - Handler

Enforces INVARIANT_CC_NO_UNUSED_OUTPUTS_V0 at compile time.

Detects unused CC outputs as code smell indicator:
- Outputs produced but never consumed
- Potential optimization opportunities
- Incomplete workflow indicators

Enforcement Level: WARNING (not ERROR)
- Build succeeds with warnings
- Warnings logged for author review

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Check for unused CC outputs against pre-computed structural analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed cc_unused_outputs

    Returns:
        Assertion result with warnings (not violations)
    """
    wf_count = 0
    all_warnings = []

    # STRICT INVERSION OF CONTROL: Compiler must provide complete context
    cc_unused_outputs = compilation_context.get("cc_unused_outputs")

    if cc_unused_outputs is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "capability_contracts::ASSERT_CC_NO_UNUSED_OUTPUTS_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing cc_unused_outputs",
                "fix": "Compiler must pre-compute CC unused outputs analysis before assert phase"
            }],
            "status": "FAILED"
        }

    # Check WF artifacts for unused outputs
    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_count += 1

    # Aggregate warnings from all per-WF analyses
    for wf_fqdn, result in cc_unused_outputs.items():
        warnings = result.get("warnings", [])
        if warnings:
            for warning in warnings:
                all_warnings.append({
                    "fqdn": wf_fqdn,
                    "rule": "capability_contracts::INVARIANT_CC_NO_UNUSED_OUTPUTS_V0",
                    "message": warning.get("violation", warning.get("message", "Unknown unused output warning")),
                    "fix": warning.get("fix", "Remove unused output or connect it to a consumer")
                })

    if all_warnings:
        return {
            "assert_count": wf_count,
            "violations": [],  # No violations - warnings are not blocking
            "warnings": all_warnings,
            "warning_count": len(all_warnings),
            "status": "PASSED"  # PASSED with warnings
        }

    return {
        "assert_count": wf_count,
        "violations": [],
        "warnings": [],
        "status": "PASSED"
    }
