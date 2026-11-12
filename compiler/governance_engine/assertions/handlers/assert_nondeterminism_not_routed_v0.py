"""
ASSERT_NONDETERMINISM_NOT_ROUTED_V0 Handler

A non-deterministic atom's results are offered, never decided. A capability contract routes on the
outcome of its steps, so a non-deterministic atom may not be one of them; and a molecule's emission,
which is what a contract receives, may not come from one. A deterministic step stands between the
atom and every route.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._transform_index import (
    NONDETERMINISTIC_PURITY, index, kind, machine, purity, step_target, steps, transforms,
)

ASSERT = "ASSERT_NONDETERMINISM_NOT_ROUTED_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    idx = index(artifacts)
    checked = 0

    for cc in (a for a in artifacts if a.get("artifact_type") == "CC"):
        checked += 1
        pipeline = cc.get("frontmatter", {}).get("core", {}).get("pipeline", []) or []
        for step in pipeline:
            if not isinstance(step, dict) or not step.get("transform"):
                continue
            target = idx.get(step["transform"])
            if target is not None and kind(target) == "atom" and purity(target) == NONDETERMINISTIC_PURITY:
                violations.append({
                    "assert": ASSERT, "artifact": cc.get("artifact_code", "UNKNOWN"),
                    "violation": (f"step {step.get('step')!r} invokes {step['transform']!r}, a "
                                  f"non-deterministic atom, so the contract would route on what it said"),
                    "fix": "Invoke a molecule whose emission comes from a deterministic step",
                })

    for mol in (ct for ct in transforms(artifacts) if kind(ct) == "molecule"):
        checked += 1
        emit = machine(mol).get("emit")
        if not isinstance(emit, dict):
            continue
        by_symbol = {s.get("as"): s for s in steps(mol) if s.get("as")}
        for out, symbol in emit.items():
            step = by_symbol.get(symbol)
            if step is None or step.get("kind") != "atom":
                continue
            target = idx.get(step_target(step))
            if target is not None and purity(target) == NONDETERMINISTIC_PURITY:
                violations.append({
                    "assert": ASSERT, "artifact": mol.get("artifact_code", "UNKNOWN"),
                    "violation": (f"emits {out!r} directly from {step_target(step)!r}, a "
                                  f"non-deterministic atom"),
                    "fix": "Emit from a deterministic step that consumes the atom's result",
                })

    return {"assert_count": checked, "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
