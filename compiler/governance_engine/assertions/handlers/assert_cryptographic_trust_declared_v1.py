"""
ASSERT_CRYPTOGRAPHIC_TRUST_DECLARED_V1 Handler

Enforces INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V1: a composition carries exactly one cryptographic
trust structure, and therefore declares exactly one trust mode.

Differs from V0 in what it counts, as the placement handler's V1 did. V0 selected by `status: active`
on the structure, which made the trust mode a property of the surface's inventory: a surface
declaring a signed mode beside the unsigned one was malformed, even when the compositions built from
it each wanted one. V1 counts what the composition carries. The surface may declare every authorized
mode, and the build's selection reduces them to one.
"""

_ASSERT = "cryptographic_trust::ASSERT_CRYPTOGRAPHIC_TRUST_DECLARED_V1"
_RULE = "cryptographic_trust::INVARIANT_CRYPTOGRAPHIC_TRUST_DECLARED_V1"

# No copy of the authorized modes is held here. A mode no structure declares resolves to nothing at
# selection and the build refuses, and a surface carries a structure only for a mode
# CONSTITUTION_CRYPTOGRAPHIC_TRUST_V1 §1 admits. What remains here is cardinality.


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    carried = [
        a for a in artifacts
        if a.get("namespace") == "cryptographic_trust"
        and a.get("artifact_code", "").startswith("STRUCTURE_CRYPTOGRAPHIC_TRUST_")
    ]

    violations = []

    if len(carried) == 0:
        violations.append({
            "fqdn": _ASSERT,
            "rule": _RULE,
            "message": "The composition carries no cryptographic trust structure, so it declares no "
                       "trust mode. An absent trust mode is not a default.",
            "fix": "Name a trust mode in the build configuration's trust_mode field.",
        })
    elif len(carried) > 1:
        codes = sorted(a.get("artifact_code") for a in carried)
        violations.append({
            "fqdn": _ASSERT,
            "rule": _RULE,
            "message": f"The composition carries {len(carried)} trust structures: {codes}. Exactly one "
                       "is permitted — two are two answers to what the composition must be trusted by.",
            "fix": "The build selects one mode and the compiler materializes only that structure; "
                   "more than one reaching the composition is a materialization fault, not a "
                   "configuration one.",
        })
    elif not (carried[0].get("frontmatter", {}) or {}).get("trust_mode"):
        violations.append({
            "fqdn": _ASSERT,
            "rule": _RULE,
            "message": "The carried trust structure declares no trust_mode, so the composition "
                       "declares no posture.",
            "fix": "A trust structure declares its mode in trust_mode.",
        })

    return {
        "assert_count": len(carried),
        "violations": violations,
        "status": "PASSED" if not violations else "FAILED",
    }
