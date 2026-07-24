"""
ASSERT_IDENTITY_MIGRATION_CROSSCHECK_V0 Handler — TEMPORARY (semantic-alignment migration).

Proves the switch from path-derived identity to declared identity changed no FQDN value:
every artifact's declared identity (fqdn_id) must equal the path-derived value the compiler
still computes for cross-check (metadata.derived_fqdn).

This exists ONLY to gate the migration. It is retired once the no-op is proven — leaving it
permanent would keep the folder secretly authoritative over identity.
"""

RULE = "fb.constitution::INVARIANT_IDENTITY_MIGRATION_CROSSCHECK_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    checked = 0
    for a in artifacts:
        derived = (a.get("metadata", {}) or {}).get("derived_fqdn", "")
        if not derived:
            continue  # imported capability / no path-derived value in this build — nothing to cross-check
        checked += 1
        declared = a.get("fqdn_id", "")
        if declared != derived:
            violations.append({
                "fqdn": declared or "unknown",
                "rule": RULE,
                "message": f"declared identity {declared!r} != path-derived {derived!r}",
                "fix": "The declared fqdn changed an identity value; restore it to the derived value "
                       "(migration preserves identity), or correct the derivation.",
            })
    return {"assert_count": checked, "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
