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

# Authorized by CONSTITUTION_EXECUTION_PLACEMENT_V1 §1. Authorizing a mode is an amendment to that
# constitution; this list is the compiler's copy of it and must not be extended here alone.
AUTHORIZED_MODES = ("LOCAL_SINGLE_NODE", "LOCAL_MULTI_WORKER")


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
    else:
        mode = (carried[0].get("frontmatter", {}) or {}).get("placement_mode")
        if mode not in AUTHORIZED_MODES:
            violations.append({
                "fqdn": _ASSERT,
                "rule": _RULE,
                "message": f"Placement mode {mode!r} is not authorized. Authorized modes are "
                           f"{list(AUTHORIZED_MODES)}.",
                "fix": "Authorizing a mode is an amendment to CONSTITUTION_EXECUTION_PLACEMENT_V1 "
                       "§1, never a configuration value.",
            })

    return {
        "assert_count": len(carried),
        "violations": violations,
        "status": "PASSED" if not violations else "FAILED",
    }
