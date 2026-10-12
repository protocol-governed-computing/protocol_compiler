"""
ASSERT_PROTOCOL_SURFACE_CLOSED_V0 Handler

Validates all FQDN references resolve to existing artifacts.
"""

from typing import Any


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    """
    Verify all FQDN references resolve to existing artifacts.

    Args:
        artifacts: All validated artifacts
        compilation_context: Contains artifacts_by_fqdn mapping

    Returns:
        {
            "assert_count": int,
            "violations": list[dict]
        }
    """
    violations = []
    artifacts_by_fqdn = compilation_context["artifacts_by_fqdn"]

    # A reference resolves if it points to an artifact in this graph OR into the imported platform
    # surface (which a domain build compiles against, resolved externally — design §3). Empty for a
    # platform build, so behaviour there is unchanged.
    available_fqdns = set(artifacts_by_fqdn.keys()) | set(
        compilation_context.get("imported_surface_fqdns", set())
    )

    for artifact in artifacts:
        fqdn = artifact["fqdn_id"]

        # Extract all FQDN references from artifact
        references = _extract_fqdn_references(artifact)

        # Check each reference exists
        for ref_fqdn in references:
            if ref_fqdn not in available_fqdns:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "surface_contract::INVARIANT_PROTOCOL_SURFACE_CLOSED_V0",
                    "message": f"Dangling FQDN reference (artifact not found): {ref_fqdn}",
                    "fix": f"Either: (1) Create missing artifact '{ref_fqdn}', OR (2) Remove reference from {fqdn}"
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


def _extract_fqdn_references(artifact: dict) -> set[str]:
    """
    The full names the artifact refers to: what S1 read from its declared reference parts.

    What names another artifact is declared, never inferred
    (artifact::VOCAB_DECLARATION_REPRESENTATION_V1). A full name anywhere else is refused at S1
    (E105), so nothing undeclared reaches here. A supersession part — `supersedes`, `superseded_by`
    — names an artifact without reaching it: it records history, so a predecessor deleted by record
    leaves it standing, and `supersession_agreement` checks it against the ledger instead.

    This scanned every FQDN-shaped string in the declaration, which read a supersession part as a
    dependency and refused the deletion of every superseded artifact.
    """
    return set(artifact.get("references") or [])
