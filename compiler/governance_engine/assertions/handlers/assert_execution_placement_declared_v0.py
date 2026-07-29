"""
ASSERT_EXECUTION_PLACEMENT_DECLARED_V0 Handler

Enforces INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0:
Every compiled snapshot must declare exactly one active placement contract
in the fb.execution_placement namespace.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    contracts = [
        a for a in artifacts
        if a.get("namespace") == "fb.execution_placement"
        and a.get("artifact_code", "").startswith("STRUCTURE_EXECUTION_PLACEMENT_")
    ]

    active = [
        a for a in contracts
        if a.get("frontmatter", {}).get("status") == "active"
    ]

    if len(active) == 1:
        return {
            "assert_count": len(contracts),
            "violations": [],
            "status": "PASSED",
        }

    violations = []

    if len(active) == 0:
        violations.append({
            "fqdn": "fb.execution_placement::ASSERT_EXECUTION_PLACEMENT_DECLARED_V0",
            "rule": "fb.execution_placement::INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0",
            "message": "No active placement contract found in FB_EXECUTION_PLACEMENT",
            "fix": "Add a placement contract with status: active to execution_placement/",
        })
    else:
        active_codes = [a.get("artifact_code") for a in active]
        violations.append({
            "fqdn": "fb.execution_placement::ASSERT_EXECUTION_PLACEMENT_DECLARED_V0",
            "rule": "fb.execution_placement::INVARIANT_EXECUTION_PLACEMENT_DECLARED_V0",
            "message": f"Multiple active placement contracts found: {active_codes}. Exactly one is required.",
            "fix": "Set status: active on exactly one placement contract; mark others inactive.",
        })

    return {
        "assert_count": len(contracts),
        "violations": violations,
        "status": "FAILED",
    }