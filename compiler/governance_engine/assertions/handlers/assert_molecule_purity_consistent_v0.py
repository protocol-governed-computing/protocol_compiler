"""
ASSERT_MOLECULE_PURITY_CONSISTENT_V0 Handler

A molecule's declared purity agrees with its steps. The declaration is what a reader relies on to see
where determinism ends; a molecule claiming determinism while containing a step that is not would
hide the one place the reader most needs to see.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._transform_index import (
    NONDETERMINISTIC_PURITY, index, kind, purity, reachable, transforms,
)

ASSERT = "ASSERT_MOLECULE_PURITY_CONSISTENT_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    idx = index(artifacts)
    molecules = [ct for ct in transforms(artifacts) if kind(ct) == "molecule"]
    for mol in molecules:
        if purity(mol) == NONDETERMINISTIC_PURITY:
            continue
        for step in reachable(mol, idx):
            if purity(step) == NONDETERMINISTIC_PURITY:
                violations.append({
                    "assert": ASSERT, "artifact": mol.get("artifact_code", "UNKNOWN"),
                    "violation": (f"declares {purity(mol)!r} and reaches "
                                  f"{step.get('artifact_code')!r}, which declares it is not "
                                  f"deterministic"),
                    "fix": "Declare the molecule ct_impure, so a reader sees where determinism ends",
                })
    return {"assert_count": len(molecules), "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
