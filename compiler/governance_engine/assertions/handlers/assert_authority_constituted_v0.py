"""
ASSERT_AUTHORITY_CONSTITUTED_V0 - Handler

Every authority an artifact declares must be constituted by a declared constituting act.

`2e` CA-2: an authority "MUST NOT be constituted by need, precedence, containment, naming, or
classification." An authority that exists because artifacts name it is constituted by need.

Not an allowlist. The condition is enforced, never a permitted set — CA-3 and the ruling's clause 5
both refuse a whitelist.

CONSTITUTIONAL: Pure rule checker — reads artifact frontmatter only
"""

RULE = "ASSERT_AUTHORITY_CONSTITUTED_V0"


def _fm(artifact: dict) -> dict:
    return artifact.get("frontmatter") or {}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    constituted: set[str] = set()
    for a in artifacts:
        declared = _fm(a).get("constitutes_authority")
        if isinstance(declared, str):
            constituted.add(declared)
        elif isinstance(declared, list):
            constituted.update(x for x in declared if isinstance(x, str))

    violations = []
    checked = 0
    for a in artifacts:
        authority = _fm(a).get("authority")
        if not authority:
            continue
        checked += 1
        if authority not in constituted:
            violations.append({
                "fqdn": a.get("fqdn_id", "UNKNOWN"),
                "rule": "federation::INVARIANT_AUTHORITY_CONSTITUTED_V0",
                "message": (
                    f"declares authority {authority!r}, which no constituting act declares. "
                    f"An authority constituted by being named is constituted by need (2e CA-2)."
                ),
                "fix": (
                    f"Declare `constitutes_authority: {authority}` on the CONSTITUTION that "
                    f"constitutes it, or declare an authority that exists."
                ),
            })

    return {
        "assert_count": checked,
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
