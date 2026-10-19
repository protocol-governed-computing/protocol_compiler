"""
ASSERT_TEST_DATA_MATCH_CT_OUTPUT_V0 Handler

A vector's expected outputs are outputs its target transform declares. A case expecting SUCCESS states,
for every output the transform declares, either the value it must have or an assertion on its form, and
states nothing the transform does not declare. A case expecting VIOLATION states no outputs: a refusal
yields none.

The target is the transform the vector names, and its outputs are the transform's own declared outputs.
The check this replaces compared against a capability contract it took to be the transform's governor —
the first entry of its `governed_by`, which in this composition is a constitution — and so could not
have judged a vector correctly had it ever been given one.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._test_data import cases, target, vectors
from compiler.governance_engine.assertions.handlers._transform_index import index

ASSERT = "ASSERT_TEST_DATA_MATCH_CT_OUTPUT_V0"


def _declared_outputs(ct: dict) -> set[str]:
    outputs = ct.get("frontmatter", {}).get("core", {}).get("outputs", {})
    return set(outputs) if isinstance(outputs, dict) else set()


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    idx = index(artifacts)
    checked = 0

    def refuse(vector, message, fix):
        violations.append({"assert": ASSERT, "artifact": vector.get("artifact_code", "UNKNOWN"),
                           "violation": message, "fix": fix})

    for vector in vectors(artifacts):
        checked += 1
        tested = idx.get(target(vector))
        if tested is None:
            refuse(vector, f"targets {target(vector)!r}, which is not a transform this build declares",
                   "Name the transform the vector tests by its FQDN")
            continue
        declared = _declared_outputs(tested)
        for case in cases(vector):
            stated = set(case.get("expected") or {}) | set(case.get("assertions") or {})
            case_id = case.get("case_id")
            if case.get("expected_outcome") == "VIOLATION":
                if stated:
                    refuse(vector, f"case {case_id!r} expects a refusal and states outputs {sorted(stated)}",
                           "A refusal yields no outputs; state none")
                continue
            missing, extra = declared - stated, stated - declared
            if missing:
                refuse(vector, f"case {case_id!r} states nothing for declared outputs {sorted(missing)}",
                       "State each declared output's value, or an assertion on its form")
            if extra:
                refuse(vector, f"case {case_id!r} states outputs {tested.get('artifact_code')} does not "
                               f"declare: {sorted(extra)}",
                       "State only outputs the transform declares")
    return {"assert_count": checked, "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
