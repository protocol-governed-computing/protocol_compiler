"""
A transform is given only values of the types it declares.

`ASSERT_CT_INPUT_TYPED_V0` compares each input a contract binds to a transform step with the type the
transform declares: a literal by its value, `$.inputs.<field>` by the contract's declaration, and
`$.results.<step>.<name>` by what the earlier step's transform declares for the output it maps to
that name. `any`, an undeclared source and a transform the build cannot see are not compared. A
contract not in force is not checked.

Run:  python scripts/testbed/test_input_typed.py
"""
import sys

from compiler.governance_engine.assertions.handlers.assert_ct_input_typed_v0 import execute as typed

CHECK = {"core": {"inputs": {"sequences": {"type": "object"}},
                  "outputs": {"all_terminate": {"type": "boolean"}}}}
REQUIRE_TRUE = {"core": {"inputs": {"value": {"type": "boolean"}}, "outputs": {"held": {"type": "boolean"}}}}
MEMBERSHIP = {"core": {"inputs": {"value": {"type": "string"}, "allowed_set": {"type": "array"}}}}
RATIO = {"core": {"inputs": {"x": {"type": "number"}, "anything": {"type": "any"}}}}
CONTEXT = {"imported_frontmatter": {"p::CT_CHECK": CHECK, "p::CT_REQUIRE_TRUE": REQUIRE_TRUE,
                                    "p::CT_MEMBERSHIP": MEMBERSHIP, "p::CT_RATIO": RATIO}}


def cc(pipeline, inputs=None, superseded=False):
    frontmatter = {"core": {"inputs": inputs or {"sequences": {"type": "object"}}, "pipeline": pipeline}}
    if superseded:
        frontmatter["superseded_by"] = ["probe::CC_GATE_V1"]
    return {"artifact_type": "CC", "fqdn_id": "probe::CC_GATE_V0", "frontmatter": frontmatter}


CHECK_STEP = {"step": "check", "transform": "p::CT_CHECK", "inputs": {"sequences": "$.inputs.sequences"},
              "outputs": {"all_terminate": "$.capability_result.all_terminate"}}


def found(*artifacts):
    return [v["message"] for v in typed(list(artifacts), CONTEXT)["violations"]]


def test_a_boolean_given_to_a_boolean_passes():
    gate = cc([CHECK_STEP, {"step": "decide", "transform": "p::CT_REQUIRE_TRUE",
                            "inputs": {"value": "$.results.check.all_terminate"}}])
    assert found(gate) == []


def test_a_boolean_given_to_a_string_is_refused():
    gate = cc([CHECK_STEP, {"step": "decide", "transform": "p::CT_MEMBERSHIP",
                            "inputs": {"value": "$.results.check.all_terminate", "allowed_set": [True]}}])
    assert found(gate) == ["Step 'decide' gives p::CT_MEMBERSHIP input 'value' a boolean; "
                           "the transform declares string"], found(gate)


def test_a_literal_is_compared_by_its_value():
    gate = cc([{"step": "decide", "transform": "p::CT_MEMBERSHIP",
                "inputs": {"value": True, "allowed_set": "not a list"}}])
    assert len(found(gate)) == 2, found(gate)


def test_a_contract_input_is_compared_by_its_declaration():
    gate = cc([{"step": "check", "transform": "p::CT_CHECK", "inputs": {"sequences": "$.inputs.sequences"}}],
              inputs={"sequences": {"type": "array"}})
    assert any("a array; the transform declares object" in m for m in found(gate)), found(gate)


def test_an_integer_satisfies_number_and_any_takes_anything():
    gate = cc([{"step": "r", "transform": "p::CT_RATIO", "inputs": {"x": 3, "anything": "text"}}])
    assert found(gate) == []


def test_an_unseen_transform_or_undeclared_source_is_not_compared():
    gate = cc([{"step": "a", "transform": "p::CT_UNSEEN", "inputs": {"value": 1}},
               {"step": "b", "transform": "p::CT_REQUIRE_TRUE", "inputs": {"value": "$.results.a.x"}}])
    assert found(gate) == []


def test_a_contract_not_in_force_is_not_checked():
    gate = cc([{"step": "decide", "transform": "p::CT_REQUIRE_TRUE", "inputs": {"value": "yes"}}],
              superseded=True)
    assert found(gate) == []


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # report every test, then fail the run
            failed += 1
            print(f"  FAIL  {name}: {exc!r}"[:1500])
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
