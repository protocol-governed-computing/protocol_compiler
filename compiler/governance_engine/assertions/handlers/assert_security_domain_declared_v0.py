"""
ASSERT_SECURITY_DOMAIN_DECLARED_V0 Handler

Enforces INVARIANT_SECURITY_DOMAIN_DECLARED_V0:
Every compiled snapshot must declare exactly one active security domain contract
in the fb.security_domain namespace.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    contracts = [
        a for a in artifacts
        if a.get("namespace") == "fb.security_domain"
        and a.get("artifact_code", "").startswith("STRUCTURE_SECURITY_DOMAIN_")
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
            "fqdn": "fb.security_domain::ASSERT_SECURITY_DOMAIN_DECLARED_V0",
            "rule": "fb.security_domain::INVARIANT_SECURITY_DOMAIN_DECLARED_V0",
            "message": "No active security domain contract found in FB_SECURITY_DOMAIN",
            "fix": "Add a security domain contract with status: active to execution/envelope/security_domain/",
        })
    else:
        active_codes = [a.get("artifact_code") for a in active]
        violations.append({
            "fqdn": "fb.security_domain::ASSERT_SECURITY_DOMAIN_DECLARED_V0",
            "rule": "fb.security_domain::INVARIANT_SECURITY_DOMAIN_DECLARED_V0",
            "message": f"Multiple active security domain contracts found: {active_codes}. Exactly one is required.",
            "fix": "Set status: active on exactly one security domain contract; mark others inactive.",
        })

    return {
        "assert_count": len(contracts),
        "violations": violations,
        "status": "FAILED",
    }