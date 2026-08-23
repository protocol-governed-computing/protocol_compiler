"""
ASSERT_CONCERN_NOT_AUTHORITY_V0 - Handler

The set of declared concerns and the set of declared authorities must be disjoint.

`2e` CA-6: "A concern classification MUST NOT constitute an authority or a jurisdiction."
AUTHORITY_VS_CONCERN_RULING clause 2 states the same. The defect this was written for is a concern
name promoted to a boundary — the surface carried twenty-six of them.

This predicate was unwritable while concern and authority were one identifier: no check could
distinguish an unlisted namespace from an illegitimate boundary. With separate carriers it is a set
comparison.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only
"""

RULE = "ASSERT_CONCERN_NOT_AUTHORITY_V0"


def _fm(artifact: dict) -> dict:
    return artifact.get("frontmatter") or {}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    concerns = {c for a in artifacts if (c := _fm(a).get("concern"))}
    violations = []
    checked = 0
    for a in artifacts:
        authority = _fm(a).get("authority")
        if not authority:
            continue
        checked += 1
        if authority in concerns:
            violations.append({
                "fqdn": a.get("fqdn_id", "UNKNOWN"),
                "rule": "federation::INVARIANT_CONCERN_NOT_AUTHORITY_V0",
                "message": (
                    f"declares authority {authority!r}, which is also declared as a concern. "
                    f"A concern classification does not constitute an authority (2e CA-6)."
                ),
                "fix": (
                    "Name the authority from which jurisdiction derives, not the subject governed. "
                    "A concern may be governed without constituting a boundary."
                ),
            })

    return {
        "assert_count": checked,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
