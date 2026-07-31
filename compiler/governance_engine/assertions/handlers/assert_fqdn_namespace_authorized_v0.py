"""
ASSERT_FQDN_NAMESPACE_AUTHORIZED_V0 Handler.

Identity is declared by the artifact; the namespace it declares MUST belong to the authorized
namespace set (the identity rules, repurposed from derivation to authorization). This is the
permanent guard that replaces path-derivation: a file may live anywhere, but it may not declare
an unauthorized namespace.
"""

RULE = "fb.artifact::INVARIANT_FQDN_NAMESPACE_AUTHORIZED_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    authorized = set(compilation_context.get("authorized_namespaces", []) or [])
    # Empty allowlist (e.g. a probe build) → nothing to enforce against; do not fail spuriously.
    if not authorized:
        return {"assert_count": 0, "violations": [], "status": "PASSED"}

    violations = []
    for a in artifacts:
        fqdn = a.get("fqdn_id", "")
        if "::" not in fqdn:
            continue
        ns = fqdn.split("::", 1)[0]
        # Imported artifacts carry their origin namespace (resolved externally) — not this build's
        # allowlist; skip them.
        if (a.get("metadata", {}) or {}).get("imported"):
            continue
        if ns not in authorized:
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
                "message": f"declared namespace {ns!r} is not authorized",
                "fix": f"Declare an authorized namespace, or add {ns!r} to the identity "
                       f"authorization set (STRUCTURE_IDENTITY_V0 / domain identity_rules).",
            })
    return {"assert_count": len(artifacts), "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
