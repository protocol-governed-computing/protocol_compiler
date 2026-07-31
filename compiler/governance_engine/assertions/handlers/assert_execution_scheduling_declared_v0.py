"""
ASSERT_EXECUTION_SCHEDULING_DECLARED_V0 Handler

Enforces INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0:
Every compiled snapshot must declare exactly one active scheduling contract
in the fb.execution_scheduling namespace.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    contracts = [
        a for a in artifacts
        if a.get("namespace") == "fb.execution_scheduling"
        and a.get("artifact_code", "").startswith("STRUCTURE_EXECUTION_SCHEDULING_")
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
            "fqdn": "fb.execution_scheduling::ASSERT_EXECUTION_SCHEDULING_DECLARED_V0",
            "rule": "fb.execution_scheduling::INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0",
            "message": "No active scheduling contract found in FB_EXECUTION_SCHEDULING",
            "fix": "Add a scheduling contract with status: active to execution_scheduling/",
        })
    else:
        active_codes = [a.get("artifact_code") for a in active]
        violations.append({
            "fqdn": "fb.execution_scheduling::ASSERT_EXECUTION_SCHEDULING_DECLARED_V0",
            "rule": "fb.execution_scheduling::INVARIANT_EXECUTION_SCHEDULING_DECLARED_V0",
            "message": f"Multiple active scheduling contracts found: {active_codes}. Exactly one is required.",
            "fix": "Set status: active on exactly one scheduling contract; mark others inactive.",
        })

    return {
        "assert_count": len(contracts),
        "violations": violations,
        "status": "FAILED",
    }
