"""
ASSERT_CRYPTOGRAPHIC_TRUST_DECLARED_V0 Handler

Enforces INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V0:
Every compiled snapshot must declare exactly one active trust contract
in the cryptographic_trust namespace.
"""


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    contracts = [
        a for a in artifacts
        if a.get("namespace") == "cryptographic_trust"
        and a.get("artifact_code", "").startswith("STRUCTURE_CRYPTOGRAPHIC_TRUST_")
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
            "fqdn": "cryptographic_trust::ASSERT_CRYPTOGRAPHIC_TRUST_DECLARED_V0",
            "rule": "cryptographic_trust::INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V0",
            "message": "No active trust contract found in FB_CRYPTOGRAPHIC_TRUST",
            "fix": "Add a trust contract with status: active to cryptographic_trust/",
        })
    else:
        active_codes = [a.get("artifact_code") for a in active]
        violations.append({
            "fqdn": "cryptographic_trust::ASSERT_CRYPTOGRAPHIC_TRUST_DECLARED_V0",
            "rule": "cryptographic_trust::INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V0",
            "message": f"Multiple active trust contracts found: {active_codes}. Exactly one is required.",
            "fix": "Set status: active on exactly one trust contract; mark others inactive.",
        })

    return {
        "assert_count": len(contracts),
        "violations": violations,
        "status": "FAILED",
    }