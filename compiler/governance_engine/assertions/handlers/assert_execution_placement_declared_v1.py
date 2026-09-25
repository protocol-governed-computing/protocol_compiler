"""
ASSERT_EXECUTION_PLACEMENT_DECLARED_V1 Handler

Enforces INVARIANT_EXECUTION_PLACEMENT_DECLARED_V1: a composition carries exactly one execution
placement structure, and therefore records exactly one placement mode.

Differs from V0 in what it counts rather than in how it counts. V0 selected by `status: active` on
the artifact, which made placement a property of the surface's inventory — a surface declaring two
modes was malformed, even when the two compositions built from it each wanted one. V1 counts what
the composition carries: the surface may declare every authorized mode, and the build's selection
is what reduces them to one.

The consequences of failure therefore differ, and the diagnostics say so. Under V0, two structures
meant a surface someone had misconfigured. Under V1, two structures mean a compiler that
materialized more than its build configuration selected — which is the more dangerous of the two,
because the configuration would read as correct while the composition carried permissions it was
never granted.
"""

_ASSERT = "execution_placement::ASSERT_EXECUTION_PLACEMENT_DECLARED_V1"
_RULE = "execution_placement::INVARIANT_EXECUTION_PLACEMENT_DECLARED_V1"

# No copy of the authorized modes is held here. It was, and that was a second place for the set to
# disagree with the constitution that declares it. Authorization is enforced where it can only be
# stated once: a mode no structure declares resolves to nothing at selection and the build refuses,
# and a surface carries a structure only for a mode CONSTITUTION_EXECUTION_PLACEMENT_V1 §1 admits.
# What remains here is cardinality, which is what the invariant actually says.


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    carried = [
        a for a in artifacts
        if a.get("namespace") == "execution_placement"
        and a.get("artifact_code", "").startswith("STRUCTURE_EXECUTION_PLACEMENT_")
    ]

    violations = []

    if len(carried) == 0:
        violations.append({
            "fqdn": _ASSERT,
            "rule": _RULE,
            "message": "The composition carries no execution placement structure, so it records no "
                       "placement mode. An absent placement is not a default.",
            "fix": "Name a placement mode in the build configuration's execution_placement field.",
        })
    elif len(carried) > 1:
        codes = sorted(a.get("artifact_code") for a in carried)
        violations.append({
            "fqdn": _ASSERT,
            "rule": _RULE,
            "message": f"The composition carries {len(carried)} placement structures: {codes}. "
                       "Exactly one is permitted — two are two answers to where execution runs.",
            "fix": "The build selects one mode and the compiler materializes only that structure; "
                   "more than one reaching the composition is a materialization fault, not a "
                   "configuration one.",
        })
    elif not (carried[0].get("frontmatter", {}) or {}).get("placement_mode"):
        violations.append({
            "fqdn": _ASSERT,
            "rule": _RULE,
            "message": "The carried placement structure declares no placement_mode, so the "
                       "composition records no arrangement.",
            "fix": "A placement structure declares its mode in placement_mode.",
        })

    return {
        "assert_count": len(carried),
        "violations": violations,
        "status": "PASSED" if not violations else "FAILED",
    }
