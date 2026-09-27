"""
ASSERT_CONFORMANCE_ASSERTION_MODE_VALID_V1 Handler

Every assertion a vector's case makes uses a declared mode and type. V0 of the invariant was bound to
a compiler phase that does not exist and its check passed without reading a vector; this one reads
every case's assertions and can refuse.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._test_data import cases, vectors

ASSERT = "ASSERT_CONFORMANCE_ASSERTION_MODE_VALID_V1"

# type -> (required fields, optional fields), per mode. Declared by the invariant; restated here only
# because a handler is the invariant's mechanism.
TYPES = {
    "property": {
        "hex_string": (set(), {"byte_length"}),
        "byte_length_range": ({"min", "max"}, set()),
        "non_zero": (set(), set()),
    },
    "schema": {
        "json_schema": ({"schema_ref"}, set()),
    },
}
MODES = {"exact", "property", "schema"}


def _problems(spec) -> list[str]:
    if not isinstance(spec, dict):
        return ["an assertion is a mapping of mode, type and its fields"]
    mode = spec.get("mode")
    if mode not in MODES:
        return [f"mode {mode!r} is not one of {sorted(MODES)}"]
    if mode == "exact":
        extra = set(spec) - {"mode"}
        return [f"exact declares no fields, found {sorted(extra)}"] if extra else []
    kind = spec.get("type")
    if kind not in TYPES[mode]:
        return [f"type {kind!r} is not one of {sorted(TYPES[mode])} for mode {mode!r}"]
    required, optional = TYPES[mode][kind]
    out = [f"{kind} requires {name!r}" for name in sorted(required - set(spec))]
    extra = set(spec) - {"mode", "type"} - required - optional
    if extra:
        out.append(f"{kind} declares no field {sorted(extra)}")
    return out


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    checked = 0
    for vector in vectors(artifacts):
        for case in cases(vector):
            for field, spec in (case.get("assertions") or {}).items():
                checked += 1
                for problem in _problems(spec):
                    violations.append({
                        "assert": ASSERT, "artifact": vector.get("artifact_code", "UNKNOWN"),
                        "violation": f"case {case.get('case_id')!r}, field {field!r}: {problem}",
                        "fix": "Use a mode and type the invariant declares, with exactly its fields",
                    })
    return {"assert_count": checked, "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
