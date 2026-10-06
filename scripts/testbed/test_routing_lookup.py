"""
Routing is a lookup with two answers, and a contract declares no condition.

`ASSERT_TOPOLOGY_CONTRACT_CLOSED_V0` admitted a third routing answer, an evaluation target, and
counted its `on_true`/`on_false` as the contract's exits. Nothing ran it, so a contract routing to one
ended with its last step's outcome. `ASSERT_TOPOLOGY_CONTRACT_CLOSED_V1` refuses any answer but
`continue` and `exit`, refuses an `evaluation` block, and counts exits only from those two answers. A
contract not in force is not checked: it runs nowhere and stays as it was sealed.

Run:  python scripts/testbed/test_routing_lookup.py
"""
import sys

from compiler.governance_engine.assertions.handlers.assert_topology_contract_closed_v1 import (
    execute as contract_closed)


def cc(pipeline, allowed=("SUCCESS", "VIOLATION"), evaluation=None, superseded=False):
    core = {"pipeline": pipeline, "result_status_contract": {"allowed": list(allowed)}}
    if evaluation:
        core["evaluation"] = evaluation
    frontmatter = {"core": core}
    if superseded:
        frontmatter["superseded_by"] = ["probe::CC_GATE_V1"]
    return {"artifact_type": "CC", "fqdn_id": "probe::CC_GATE_V0", "frontmatter": frontmatter}


def step(name, routes, surface=("SUCCESS", "VIOLATION")):
    return {"step": name, "result_surface": list(surface), "on_result": routes}


CONDITION = {"evaluate_x": {"condition": "$.capability_result.ok == true",
                            "on_true": "SUCCESS", "on_false": "VIOLATION"}}


def messages(*artifacts):
    return [v["message"] for v in contract_closed(list(artifacts), {})["violations"]]


def test_a_closed_contract_of_two_answers_passes():
    gate = cc([step("check", {"SUCCESS": "continue", "VIOLATION": "exit"}),
               step("decide", {"SUCCESS": "continue", "VIOLATION": "exit"})])
    assert messages(gate) == []


def test_routing_to_a_condition_is_refused_by_step_and_answer():
    gate = cc([step("check", {"SUCCESS": "evaluate_x", "VIOLATION": "exit"})], evaluation=CONDITION)
    found = messages(gate)
    assert any("step 'check' routes 'SUCCESS' to 'evaluate_x'" in m for m in found), found
    assert any("declares an evaluation block (evaluate_x)" in m for m in found), found


def test_a_condition_no_longer_counts_as_an_exit():
    # V0 counted on_true SUCCESS as reachable; V1 reads SUCCESS as unreachable here.
    gate = cc([step("check", {"SUCCESS": "evaluate_x", "VIOLATION": "exit"})], evaluation=CONDITION)
    assert any("'SUCCESS'" in m and "unreachable" in m for m in messages(gate)), messages(gate)


def test_a_contract_not_in_force_is_not_checked():
    gate = cc([step("check", {"SUCCESS": "evaluate_x", "VIOLATION": "exit"})], evaluation=CONDITION,
              superseded=True)
    assert contract_closed([gate], {}) == {"assert_count": 0, "violations": [], "status": "PASSED"}


def test_uncontracted_and_unreachable_exits_are_still_refused():
    gate = cc([step("check", {"SUCCESS": "exit", "VIOLATION": "exit"})], allowed=("SUCCESS", "NOT_FOUND"))
    found = messages(gate)
    assert any("'VIOLATION'" in m and "uncontracted" in m for m in found), found
    assert any("'NOT_FOUND'" in m and "unreachable" in m for m in found), found


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
