"""
Transform conformance — the compiler's half of software_governance/dossiers/transform_conformance.

Each refusal the vector assertions declare is shown to fire on a vector built to trip it, and to stay
silent on one that keeps the rule: a check that has only ever been seen green has not been seen to
check anything — which is how the rule these replace passed for as long as it existed.
"""

import sys

from compiler.governance_engine.assertions.handlers.assert_conformance_assertion_mode_valid_v1 import execute as assertion_modes
from compiler.governance_engine.assertions.handlers.assert_test_data_records_match_purity_v0 import execute as records_match
from compiler.governance_engine.assertions.handlers.assert_test_data_match_ct_output_v0 import execute as output_match
from compiler.governance_engine.assertions.handlers.assert_ct_test_data_outcome_declared_v0 import execute as outcome_declared
from compiler.stages.s7_materialize import _conformance_cases

NS = "probe"
MOL = "capability_transforms::CONSTITUTION_MOLECULES_V0"


def atom(code, purity="ct_pure", outputs=("candidates",)):
    return {"artifact_type": "CT", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"core": {"outputs": {o: {"type": "array"} for o in outputs}},
                            "machine": {"ct_kind": "atom", "ct_purity": purity,
                                        "implementation": {"module": "m", "callable": "execute"}}}}


def molecule(code, stream, purity="ct_impure"):
    return {"artifact_type": "CT", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"governed_by": MOL, "machine": {"ct_kind": "molecule", "ct_purity": purity,
                                                            "atom_stream": stream}}}


def vector(target, *cases):
    return {"artifact_type": "TEST_DATA", "artifact_code": "TEST_DATA_PROBE_V0",
            "fqdn_id": f"{NS}::TEST_DATA_PROBE_V0",
            "frontmatter": {"target": f"{NS}::{target}", "cases": list(cases)}}


def case(recorded=None, assertions=None, expected=None, outcome="SUCCESS"):
    out = {"case_id": "c", "expected_outcome": outcome, "bindings": {}}
    if expected is not None:
        out["expected"] = expected
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


def test_a_case_states_exactly_the_outputs_its_target_declares():
    exact = vector("CT_IMPURE_OFFER_V0", case(assertions={"candidates": {"mode": "property", "type": "non_zero"}}))
    assert found(output_match, COMPOSITION + [exact]) == []
    missing = vector("CT_IMPURE_OFFER_V0", case(expected={}))
    assert any("states nothing for declared outputs" in v for v in found(output_match, COMPOSITION + [missing]))
    extra = vector("CT_IMPURE_OFFER_V0", case(expected={"candidates": [], "bonus": 1}))
    assert any("does not declare" in v for v in found(output_match, COMPOSITION + [extra]))
    refusal = vector("CT_IMPURE_OFFER_V0", case(outcome="VIOLATION", expected={"candidates": []}))
    assert any("expects a refusal" in v for v in found(output_match, COMPOSITION + [refusal]))
    nowhere = {**vector("CT_IMPURE_OFFER_V0", case()), "frontmatter": {"target": "probe::CT_NONE_V0", "cases": [case()]}}
    assert any("not a transform" in v for v in found(output_match, COMPOSITION + [nowhere]))


def test_every_case_declares_its_outcome():
    assert found(outcome_declared, [vector("CT_PURE_CHOOSE_V0", case())]) == []
    assert len(found(outcome_declared, [vector("CT_PURE_CHOOSE_V0", case(outcome=None))])) == 1


SEALED = {"probe::CT_WRITE_V0": {"fqdn_id": "probe::CT_WRITE_V0", "artifact_type": "CT",
                                 "ct_ir": {"atom_stream": [{"atom": "x"}], "outputs": {"r": {"from": "written"}},
                                           "inputs": {"positions": {"type": "array"}}}}}


def test_a_case_is_bound_to_its_target_as_sealed_with_its_records():
    recorded = {"written[0]/offered": OFFERED}
    frontmatter = {"target": "probe::CT_WRITE_V0",
                   "cases": [{"case_id": "two_words", "expected_outcome": "SUCCESS",
                              "bindings": {"positions": [1, 2]}, "expected": {"r": "a b"},
                              "recorded": recorded}]}
    (runnable,), errors = _conformance_cases("probe::TEST_DATA_PROBE_V0", frontmatter, SEALED)
    assert errors == []
    assert runnable["ct_ir"]["atom_stream"] == [{"atom": "x"}]
    assert runnable["ct_ir"]["inputs"] == {"positions": [1, 2]}
    assert runnable["ct_ir"]["input_types"] == {"positions": "array"}
    assert runnable["recorded"] == recorded
    assert runnable["fqdn"] == "probe::CT_WRITE_V0::two_words"


def test_a_vector_that_cannot_be_bound_stops_the_build():
    _, errors = _conformance_cases("probe::TD", {"target": "probe::CT_NONE_V0", "cases": [case()]}, SEALED)
    assert len(errors) == 1 and "not a transform" in errors[0].message
    unsealed = {"probe::CT_X_V0": {"fqdn_id": "probe::CT_X_V0", "artifact_type": "CT"}}
    _, errors = _conformance_cases("probe::TD", {"target": "probe::CT_X_V0", "cases": [case()]}, unsealed)
    assert len(errors) == 1 and "no sealed form" in errors[0].message


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
