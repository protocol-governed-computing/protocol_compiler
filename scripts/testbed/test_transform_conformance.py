"""
Transform conformance — the compiler's half of software_governance/dossiers/transform_conformance.

Each refusal the vector assertions declare is shown to fire on a vector built to trip it, and to stay
silent on one that keeps the rule: a check that has only ever been seen green has not been seen to
check anything — which is how the rule these replace passed for as long as it existed.
"""

import sys

from compiler.governance_engine.assertions.handlers.assert_conformance_assertion_mode_valid_v1 import execute as assertion_modes
from compiler.governance_engine.assertions.handlers.assert_test_data_records_match_purity_v0 import execute as records_match

NS = "probe"
MOL = "capability_transforms::CONSTITUTION_MOLECULES_V0"


def atom(code, purity="ct_pure"):
    return {"artifact_type": "CT", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"machine": {"ct_kind": "atom", "ct_purity": purity,
                                        "implementation": {"module": "m", "callable": "execute"}}}}


def molecule(code, stream, purity="ct_impure"):
    return {"artifact_type": "CT", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"governed_by": MOL, "machine": {"ct_kind": "molecule", "ct_purity": purity,
                                                            "atom_stream": stream}}}


def vector(target, *cases):
    return {"artifact_type": "TEST_DATA", "artifact_code": "TEST_DATA_PROBE_V0",
            "fqdn_id": f"{NS}::TEST_DATA_PROBE_V0",
            "frontmatter": {"target": f"{NS}::{target}", "cases": list(cases)}}


def case(recorded=None, assertions=None):
    out = {"case_id": "c", "expected_outcome": "SUCCESS", "bindings": {}}
    if recorded is not None:
        out["recorded"] = recorded
    if assertions is not None:
        out["assertions"] = assertions
    return out


OFFER, CHOOSE = atom("CT_IMPURE_OFFER_V0", "ct_impure"), atom("CT_PURE_CHOOSE_V0")
PASS = molecule("CT_PASS_V0", [
    {"kind": "atom", "atom": f"{NS}::CT_IMPURE_OFFER_V0", "as": "offered"},
    {"kind": "atom", "atom": f"{NS}::CT_PURE_CHOOSE_V0", "as": "chosen"},
])
WRITE = molecule("CT_WRITE_V0", [
    {"kind": "loop", "molecule": f"{NS}::CT_PASS_V0", "as": "written", "over": "$.inputs.positions"},
])
COMPOSITION = [OFFER, CHOOSE, PASS, WRITE]
OFFERED = {"candidates": ["a", "b"]}


def found(handler, artifacts):
    return [v["violation"] for v in handler(artifacts, {})["violations"]]


def test_a_molecule_case_supplying_every_nondeterministic_step_passes():
    good = vector("CT_WRITE_V0", case({"written[0]/offered": OFFERED, "written[1]/offered": OFFERED}))
    assert found(records_match, COMPOSITION + [good]) == []


def test_a_nondeterministic_step_left_without_a_record_is_refused():
    missing = vector("CT_WRITE_V0", case({}))
    assert any("supplies no recorded result" in v for v in found(records_match, COMPOSITION + [missing]))


def test_a_record_for_a_deterministic_step_is_refused():
    wrong = vector("CT_WRITE_V0", case({"written[0]/offered": OFFERED, "written[0]/chosen": {}}))
    assert any("deterministic" in v for v in found(records_match, COMPOSITION + [wrong]))


def test_a_path_that_names_no_step_or_skips_a_pass_is_refused():
    no_step = vector("CT_WRITE_V0", case({"written[0]/offered": OFFERED, "written[0]/nowhere": {}}))
    assert any("has no step 'nowhere'" in v for v in found(records_match, COMPOSITION + [no_step]))
    no_pass = vector("CT_WRITE_V0", case({"written/offered": OFFERED}))
    assert any("names the pass" in v for v in found(records_match, COMPOSITION + [no_pass]))


def test_an_atom_is_never_replayed():
    replayed = vector("CT_IMPURE_OFFER_V0", case({"offered": OFFERED}))
    assert any("an atom is run, never replayed" in v for v in found(records_match, COMPOSITION + [replayed]))
    assert found(records_match, COMPOSITION + [vector("CT_IMPURE_OFFER_V0", case())]) == []


def test_assertions_use_declared_forms_only():
    good = vector("CT_IMPURE_OFFER_V0", case(assertions={
        "candidates": {"mode": "property", "type": "non_zero"},
        "digest": {"mode": "property", "type": "hex_string", "byte_length": 32},
    }))
    assert found(assertion_modes, [good]) == []
    for spec, expect in [
        ({"type": "non_zero"}, "mode None"),
        ({"mode": "fuzzy"}, "mode 'fuzzy'"),
        ({"mode": "property", "type": "random"}, "type 'random'"),
        ({"mode": "property", "type": "byte_length_range", "min": 1}, "requires 'max'"),
        ({"mode": "property", "type": "non_zero", "extra": 1}, "declares no field"),
    ]:
        bad = vector("CT_IMPURE_OFFER_V0", case(assertions={"f": spec}))
        assert any(expect in v for v in found(assertion_modes, [bad])), (spec, found(assertion_modes, [bad]))


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # report every test, then fail the run
            failed += 1
            print(f"  FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
