"""
ASSERT_CC_NO_MISSING_DEPENDENCIES_V0 - Handler

Enforces INVARIANT_CC_NO_MISSING_DEPENDENCIES_V0 at compile time.

Validates CC dependency ordering and reachability for all WF artifacts:
- No forward references (CC_B references CC_C that appears later)
- No cross-branch references (CC_B references CC_C on different branch)

Validation Scope: ORDERING and REACHABILITY ONLY (not field existence, not FQDN resolution)

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Validate CC dependency ordering against pre-computed structural analysis.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains pre-computed cc_dependencies

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
    cc_dependencies = compilation_context.get("cc_dependencies")

    if cc_dependencies is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "capability_contracts::ASSERT_CC_NO_MISSING_DEPENDENCIES_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing cc_dependencies",
                "fix": "Compiler must pre-compute CC dependency analysis before assert phase"
            }],
            "status": "FAILED"
        }

    # Check rules against pre-computed structure
    for artifact in artifacts:
        if artifact.get("artifact_type") != "WF":
            continue

        wf_count += 1
        fqdn = artifact["fqdn_id"]
        deps_result = cc_dependencies.get(fqdn)

        if not deps_result:
            violations.append({
                "fqdn": fqdn,
                "rule": "capability_contracts::INVARIANT_CC_NO_MISSING_DEPENDENCIES_V0",
                "message": "Missing dependency analysis for WF artifact",
                "fix": "Compiler must analyze all WF artifacts"
            })
            continue

        # Translate structural violations to standardized rule violations
        if deps_result.get("status") == "FAILED":
            for structural_violation in deps_result.get("violations", []):
                violations.append({
                    "fqdn": fqdn,
                    "rule": "capability_contracts::INVARIANT_CC_NO_MISSING_DEPENDENCIES_V0",
                    "message": structural_violation.get("violation", "Unknown CC dependency violation"),
                    "fix": structural_violation.get("fix", "Ensure all CC dependencies are satisfied")
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
