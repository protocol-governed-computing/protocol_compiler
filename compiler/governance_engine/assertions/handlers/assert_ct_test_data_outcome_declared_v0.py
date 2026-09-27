"""
ASSERT_CT_TEST_DATA_OUTCOME_DECLARED_V0 Handler

Every case of every vector declares its expected outcome: SUCCESS, or VIOLATION for a transform
expected to refuse. The compiler never defaults an absent outcome to SUCCESS — that would mask every
case written to exercise a refusal.

Cases are read from the vector's Machine block, where `SCHEMA_TEST_DATA_V0` places them; this check
once read them from prose by pattern.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._test_data import cases, vectors

ASSERT = "ASSERT_CT_TEST_DATA_OUTCOME_DECLARED_V0"
_VALID_OUTCOMES = frozenset({"SUCCESS", "VIOLATION"})


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    checked = 0
    for vector in vectors(artifacts):
        for case in cases(vector):
            checked += 1
            outcome = case.get("expected_outcome")
            if outcome not in _VALID_OUTCOMES:
                violations.append({
                    "assert": ASSERT, "artifact": vector.get("artifact_code", "UNKNOWN"),
                    "violation": (f"case {case.get('case_id')!r} declares expected_outcome "
                                  f"{outcome!r}; a case expects SUCCESS or VIOLATION"),
                    "fix": "Declare expected_outcome: SUCCESS or VIOLATION",
                })
    return {"assert_count": checked, "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
