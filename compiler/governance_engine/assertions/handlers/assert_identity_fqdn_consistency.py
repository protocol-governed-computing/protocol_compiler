"""
ASSERT Handler: Identity FQDN Consistency.

Enforces that every artifact's FQDN matches the {namespace}::{artifact_code} pattern
and that FQDNs are unique across the compilation graph.
"""

def execute(artifacts, context):
    seen = {}
    violations = []

    for artifact in artifacts:
        # Note: artifacts are normalized dicts from compilation context
        fqdn = artifact.get("fqdn_id") # compiler uses fqdn_id for full string
        code = artifact.get("artifact_code")

        if not fqdn:
            violations.append({
                "fqdn": code or "UNKNOWN",
                "rule": "governance.layers::INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0",
                "message": f"Artifact missing fqdn_id field (code: {code})",
                "fix": "Ensure artifact has fqdn_id field in format layer::artifact_code"
            })
            continue

        if "::" not in fqdn:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0",
                "message": f"Invalid FQDN format (missing :: separator): {fqdn}",
                "fix": f"Change FQDN to format layer::artifact_code"
            })
            continue

        namespace, name = fqdn.split("::")

        if name != code:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0",
                "message": f"FQDN code mismatch: name part '{name}' doesn't match artifact_code '{code}'",
                "fix": f"Change FQDN to {namespace}::{code} or change artifact_code to {name}"
            })

        if fqdn in seen:
            violations.append({
                "fqdn": fqdn,
                "rule": "governance.layers::INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0",
                "message": f"Duplicate FQDN in compilation graph: {fqdn}",
                "fix": "Ensure each artifact has a unique FQDN"
            })
        seen[fqdn] = True

        if namespace.startswith("domains."):
            parts = namespace.split(".")
            if len(parts) != 2:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "governance.layers::INVARIANT_IDENTITY_FQDN_CONSISTENCY_V0",
                    "message": f"Invalid domain namespace format: {namespace} (expected: domains.domain_name)",
                    "fix": "Change namespace to format: domains.{domain_name}"
                })

    if violations:
        return {
            "assert_count": len(artifacts),
            "violations": violations,
            "status": "FAILED"
        }

    return {
        "assert_count": len(artifacts),
        "violations": [],
        "status": "PASSED"
    }
