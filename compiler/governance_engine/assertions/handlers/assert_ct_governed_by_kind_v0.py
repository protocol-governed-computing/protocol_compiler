"""
ASSERT_CT_GOVERNED_BY_KIND_V0 Handler

Every transform is governed by exactly one of the three constitutions that govern transforms,
decided by what it declares. A transform naming the wrong one would escape the rules of the one that
describes it: a non-deterministic atom claiming the deterministic constitution would never have its
results recorded.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._transform_index import (
    CONSTITUTION_DETERMINISTIC, CONSTITUTION_MOLECULES, CONSTITUTION_NONDETERMINISTIC,
    DETERMINISTIC_PURITIES, NONDETERMINISTIC_PURITY, kind, purity, transforms,
)

ASSERT = "ASSERT_CT_GOVERNED_BY_KIND_V0"


def _expected(ct_kind: str, ct_purity: str) -> str | None:
    if ct_kind == "molecule":
        return CONSTITUTION_MOLECULES
    if ct_kind == "atom" and ct_purity in DETERMINISTIC_PURITIES:
        return CONSTITUTION_DETERMINISTIC
    if ct_kind == "atom" and ct_purity == NONDETERMINISTIC_PURITY:
        return CONSTITUTION_NONDETERMINISTIC
    return None


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    cts = transforms(artifacts)
    for ct in cts:
        code = ct.get("artifact_code", "UNKNOWN")
        ct_kind, ct_purity = kind(ct), purity(ct)
        expected = _expected(ct_kind, ct_purity)
        governed_by = ct.get("frontmatter", {}).get("governed_by", "")
        if expected is None:
            violations.append({
                "assert": ASSERT, "artifact": code,
                "violation": (f"declares kind {ct_kind!r} and purity {ct_purity!r}, which place it "
                              f"under no constitution — what it is cannot be decided"),
                "fix": "Declare ct_kind atom or molecule, and ct_purity ct_pure, ct_exec or ct_impure",
            })
        elif governed_by != expected:
            violations.append({
                "assert": ASSERT, "artifact": code,
                "violation": (f"is a {ct_kind} declaring {ct_purity}, governed by {governed_by!r}; "
                              f"what it declares places it under {expected}"),
                "fix": f"Set governed_by to {expected}",
            })
    return {"assert_count": len(cts), "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
