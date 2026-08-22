"""
ASSERT_GOVERNANCE_DECLARATION_RESOLVES_V0 Handler

Closes the governance chain in both directions:

    CONSTITUTION --declares--> INVARIANT --derives--> ASSERT --bound to--> HANDLER
    CONSTITUTION <---names---- INVARIANT

Forward: every `rules[].enforced_by` FQDN resolves to a compiled INVARIANT whose derived
ASSERT has a registered handler. Backward: every compiled INVARIANT is named by at least
one constitution rule.

The handler validates the compiler's already-resolved artifact set and the closed
HANDLER_REGISTRY. It performs no discovery of its own — an assertion that rediscovered
the corpus would drift from the compiler as the platform evolves.
"""

from typing import Any

RULE = "governance::INVARIANT_GOVERNANCE_DECLARATION_RESOLVES_V0"

# Terminal declarations: enforcement is deliberately outside the compiler. Their
# admissibility against core.enforcement_model is governed by SCHEMA_CONSTITUTION_V0.
_SENTINELS = frozenset({"PROCESS_ENFORCED", "RUNTIME_ENFORCED"})

_HANDLER_MODULE_PREFIX = "pgs_governance.registry.handlers"

# Enforcement stages whose mechanism is NOT the compiler. An invariant declaring one of these has
# no derived compile-time ASSERT to register, and requiring one would force a vacuous handler into
# the registry — a check that always passes because it is looking at the wrong scope.
#
#   runtime_outcome         bound to a CC violation outcome + WF routing; verified by
#                           ASSERT_RUNTIME_INVARIANT_WIRED_V0
#   composition_conformance evaluated by the assembler over the ASSEMBLED snapshot; admitted by
#                           the invariant's own `composition_check` declaration
#
# The invariant is still required to be named by a constitution rule (Rule 2 below): what is
# exempted is the compile-time HANDLER, never the governance closure.
_NON_COMPILER_STAGES = frozenset({"runtime_outcome", "composition_conformance"})


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    from compiler.governance_engine.assertions.handlers import HANDLER_REGISTRY

    violations: list[dict] = []

    constitutions = [a for a in artifacts if a.get("artifact_type") == "CONSTITUTION"
                     or a.get("frontmatter", {}).get("artifact_kind") == "CONSTITUTION"]
    invariants = {
        a["fqdn_id"]: a for a in artifacts
        if a.get("frontmatter", {}).get("artifact_kind") == "INVARIANT"
    }

    # Nothing to close in a build that carries no governance artifacts (domain builds
    # import governance resolve-only). Vacuous, not violated.
    if not constitutions and not invariants:
        return {"assert_count": 0, "violations": [], "status": "PASSED"}

    named: set[str] = set()

    # --- Rule 1: forward resolution -------------------------------------------------
    for con in constitutions:
        con_fqdn = con.get("fqdn_id", "unknown")
        for rule in con.get("frontmatter", {}).get("rules", []) or []:
            target = rule.get("enforced_by")
            if target in _SENTINELS:
                continue
            if not isinstance(target, str) or "::" not in target:
                violations.append({
                    "fqdn": con_fqdn,
                    "rule": RULE,
                    "message": f"rules[].enforced_by is not an FQDN or sentinel: {target!r}",
                    "fix": "Name the enforcing INVARIANT by FQDN, or declare "
                           "PROCESS_ENFORCED / RUNTIME_ENFORCED",
                })
                continue

            named.add(target)
            inv = invariants.get(target)
            if inv is None:
                violations.append({
                    "fqdn": con_fqdn,
                    "rule": RULE,
                    "message": f"rules[].enforced_by names an invariant absent from the "
                               f"compiled set: {target}",
                    "fix": f"Author {target}, or bind the rule to an invariant that exists",
                })
                continue

            stages = set(inv.get("frontmatter", {}).get("core", {}).get("enforcement_stage") or [])
            if stages & _NON_COMPILER_STAGES:
                continue  # enforced elsewhere; no derived compile-time ASSERT exists

            assert_code = "ASSERT_" + target.split("::")[-1][len("INVARIANT_"):]
            proj = inv.get("frontmatter", {}).get("assert_projection") or {}
            module = proj.get("handler") or f"{_HANDLER_MODULE_PREFIX}.{assert_code.lower()}"
            if module not in HANDLER_REGISTRY:
                violations.append({
                    "fqdn": con_fqdn,
                    "rule": RULE,
                    "message": f"{target} has no registered handler for its derived "
                               f"{assert_code} ({module})",
                    "fix": f"Register {module} in HANDLER_REGISTRY, or declare an "
                           f"assert_projection.handler override on {target}",
                })

    # --- Rule 2: reverse closure ----------------------------------------------------
    for fqdn in sorted(invariants):
        if fqdn not in named:
            violations.append({
                "fqdn": fqdn,
                "rule": RULE,
                "message": "orphan invariant — no constitution rule names it",
                "fix": "Declare a rule in the governing constitution whose enforced_by "
                       f"is {fqdn}",
            })

    return {
        "assert_count": len(constitutions) + len(invariants),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }