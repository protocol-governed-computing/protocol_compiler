"""
ASSERT_FQDN_ONLY_REFERENCES_V0 Handler

Validates that a reference part requiring a full name holds one (`namespace::artifact_code`).

Which parts require a full name is the platform's declaration, `full_name_required` in
`artifact::VOCAB_DECLARATION_REPRESENTATION_V0`. This handler kept its own list of four, and the
record of references refused short codes in a list of nine; one rule was enforced twice, from two
lists. It is enforced here, once, from the declaration, and the record only records.

CONSTITUTIONAL: Pure rule checker — reads the declaration from the compilation context.
"""

RULE = "artifact::INVARIANT_FQDN_ONLY_REFERENCES_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    representation = compilation_context.get("representation")
    if representation is None:
        return {
            "assert_count": 0,
            "violations": [{
                "fqdn": "artifact::ASSERT_FQDN_ONLY_REFERENCES_V0",
                "rule": "COMPILATION_CONTEXT_COMPLETE",
                "message": "Compilation context missing representation",
                "fix": "S1 must read the platform's declaration of what a reference is",
            }],
            "status": "FAILED",
        }

    violations = []
    for artifact in artifacts:
        fqdn = artifact["fqdn_id"]
        for place, value in representation.short_codes(artifact.get("frontmatter", {}) or {}):
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
                "message": f"'{place}' names '{value}' by short code; the part requires a full name",
                "fix": f"Write '{value}' as namespace::{value}",
            })

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
