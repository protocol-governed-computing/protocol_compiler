"""
A workflow binds only payload fields its IN gate declares.

`ASSERT_ADMISSION_COVERS_BINDINGS_V0` refuses a workflow whose nodes bind `$.payload.<field>` for a
field its start gate's `core.inputs` does not declare. A declared field that no node binds is allowed.

Run:  python scripts/testbed/test_admission_covers_bindings.py
"""
import sys

from compiler.governance_engine.assertions.handlers.assert_admission_covers_bindings_v0 import (
    execute as covers,
)


def gate(**inputs):
    return {"fqdn_id": "d::IN_REQUEST_V0", "artifact_type": "IN", "artifact_code": "IN_REQUEST_V0",
            "frontmatter": {"core": {"inputs": {k: {"type": "string", "required": v}
                                                for k, v in inputs.items()}}}}


def workflow(**bindings):
    return {"fqdn_id": "d::WF_REQUEST_V0", "artifact_type": "WF", "frontmatter": {"core": {
        "start_node": "IN_REQUEST_V0",
        "nodes": {"IN_REQUEST_V0": {"type": "IN", "code": "IN_REQUEST_V0", "next": {"ACK": "CC_RECORD_V0"}},
                  "CC_RECORD_V0": {"type": "CC", "code": "CC_RECORD_V0", "inputs": bindings}}}}}


def test_a_bound_field_the_gate_declares_passes():
    assert covers([gate(name=True), workflow(name="$.payload.name")], {})["status"] == "PASSED"


def test_a_bound_field_the_gate_does_not_declare_is_refused():
    result = covers([gate(name=True), workflow(name="$.payload.name", email="$.payload.email")], {})
    assert result["status"] == "FAILED" and len(result["violations"]) == 1, result
    assert "$.payload.email" in result["violations"][0]["message"], result


def test_a_declared_field_no_node_binds_is_allowed():
    assert covers([gate(name=True, author=True), workflow(name="$.payload.name")], {})["status"] == "PASSED"


def test_a_workflow_without_a_gate_is_not_examined_here():
    wf = workflow(name="$.payload.name")
    wf["frontmatter"]["core"]["start_node"] = "CC_RECORD_V0"
    assert covers([wf], {})["status"] == "PASSED"


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
