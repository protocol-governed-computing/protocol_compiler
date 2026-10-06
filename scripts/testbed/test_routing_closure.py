"""
A step answers every outcome its capability declares; a reachable workflow node answers every outcome
of what it runs.

`ASSERT_TOPOLOGY_ROUTING_COMPLETE_V0` checked a step's routing against the step's own
`result_surface`, which the author declares. A surface narrower than the capability passed, and the
runtime proceeded past the outcome it left out. `ASSERT_TOPOLOGY_ROUTING_COMPLETE_V1` also checks the
surface against the capability (`3d` CP-13). `ASSERT_WF_ROUTING_CLOSED_V0` is new: a workflow node that execution can
reach declares a route or an ending for every outcome of the contract or intent it runs (`4a`
GC-15). A superseded workflow and an unreachable node are not checked, because execution cannot
reach them.
"""
import sys
from types import SimpleNamespace

from compiler.governance_engine.assertions.handlers.assert_topology_routing_complete_v1 import (
    execute as routing_complete)
from compiler.governance_engine.assertions.handlers.assert_wf_routing_closed_v0 import (
    execute as checked_routing_closed)
from compiler.stages.s4_govern import _analyze_wf_routing


def routing_closed(workflows, ctx):
    """Run the GC-15 check over the routing the compiler precomputes, with S2's own resolver."""
    known = {**ctx.get("artifacts_by_fqdn", {}), **ctx.get("imported_frontmatter", {})}
    graph = SimpleNamespace(nodes={f: SimpleNamespace(artifact_code=f.split("::")[-1]) for f in known})
    code_to_fqdn = {f.split("::")[-1]: f for f in known}
    routing = {w["fqdn_id"]: _analyze_wf_routing(
        SimpleNamespace(namespace=w["namespace"], frontmatter=w["frontmatter"]), graph, code_to_fqdn)
        for w in workflows}
    return checked_routing_closed(workflows, {**ctx, "wf_routing": routing})

CS = "capability_side_effects::CS_PROBE_V0"
CT_REFUSING = "probe::CT_REFUSING_V0"
CT_TOTAL = "probe::CT_TOTAL_V0"
CS_FM = {"core": {"operations": {"WRITE": {
    "result_status_values": ["SUCCESS", "NOT_FOUND", "BACKEND_ERROR"]}}}}


def cc(fqdn, pipeline, allowed=("SUCCESS", "VIOLATION")):
    return {"artifact_type": "CC", "fqdn_id": fqdn, "namespace": fqdn.split("::")[0],
            "frontmatter": {"core": {"pipeline": pipeline,
                                     "result_status_contract": {"allowed": list(allowed)}}}}


def step(name, surface, routes=None, **capability):
    return {"step": name, **capability, "result_surface": list(surface),
            "on_result": routes if routes is not None else {c: "exit" for c in surface}}


def context(*artifacts, imported=None):
    return {"artifacts_by_fqdn": {a["fqdn_id"]: a for a in artifacts},
            "imported_frontmatter": imported or {}}


def wf(nodes, start="IN_PROBE_V0", superseded=False):
    fm = {"core": {"start_node": start, "nodes": nodes}}
    if superseded:
        fm["superseded_by"] = ["probe::WF_SUCCESSOR_V0"]
    return {"artifact_type": "WF", "fqdn_id": "probe::WF_PROBE_V0", "namespace": "probe",
            "frontmatter": fm}


INTENT = {"artifact_type": "IN", "fqdn_id": "probe::IN_PROBE_V0",
          "frontmatter": {"core": {"outcomes": {"ACK": {}, "NACK": {}}}}}


# --- CP-13 -------------------------------------------------------------------------------------

def test_a_surface_narrower_than_the_side_effect_it_dispatches_is_refused():
    c = cc("probe::CC_V0", [step("write", ["SUCCESS", "NOT_FOUND"], side_effect=CS, op="WRITE")])
    found = routing_complete([c], context(c, imported={CS: CS_FM}))["violations"]
    assert len(found) == 1 and "BACKEND_ERROR" in found[0]["message"], found


def test_a_surface_holding_everything_the_side_effect_declares_passes():
    c = cc("probe::CC_V0", [step("write", ["SUCCESS", "NOT_FOUND", "BACKEND_ERROR"],
                                 side_effect=CS, op="WRITE")])
    assert routing_complete([c], context(c, imported={CS: CS_FM}))["status"] == "PASSED"


def test_a_transform_that_can_refuse_must_have_its_refusal_in_the_surface():
    t = {"artifact_type": "CT", "fqdn_id": CT_REFUSING, "frontmatter": {"core": {"refusal": "raises"}}}
    c = cc("probe::CC_V0", [step("judge", ["SUCCESS"], transform=CT_REFUSING)])
    found = routing_complete([c, t], context(c, t))["violations"]
    assert len(found) == 1 and "VIOLATION" in found[0]["message"], found


def test_a_transform_that_never_refuses_needs_only_success():
    t = {"artifact_type": "CT", "fqdn_id": CT_TOTAL, "frontmatter": {"core": {"refusal": "never"}}}
    c = cc("probe::CC_V0", [step("shape", ["SUCCESS"], transform=CT_TOTAL)])
    assert routing_complete([c, t], context(c, t))["status"] == "PASSED"


def test_an_unrouted_surface_code_is_still_refused():
    c = cc("probe::CC_V0", [step("write", ["SUCCESS", "NOT_FOUND", "BACKEND_ERROR"],
                                 {"SUCCESS": "exit", "NOT_FOUND": "exit"}, side_effect=CS, op="WRITE")])
    found = routing_complete([c], context(c, imported={CS: CS_FM}))["violations"]
    assert len(found) == 1 and "missing routing" in found[0]["message"], found


# --- GC-15 -------------------------------------------------------------------------------------

def nodes(routes):
    return {"IN_PROBE_V0": {"type": "IN", "code": "IN_PROBE_V0",
                            "next": {"ACK": "CC_V0", "NACK": "EXIT_REJECTED"}},
            "CC_V0": {"type": "CC", "code": "CC_V0", "next": routes},
            "EXIT_DONE": {"type": "EXIT"}, "EXIT_REJECTED": {"type": "EXIT"}}


def test_a_reachable_node_that_leaves_an_outcome_unanswered_is_refused():
    c = cc("probe::CC_V0", [], allowed=("SUCCESS", "BACKEND_ERROR"))
    w = wf(nodes({"SUCCESS": "EXIT_DONE"}))
    found = routing_closed([w], context(c, INTENT))["violations"]
    assert len(found) == 1 and "'BACKEND_ERROR'" in found[0]["message"], found


def test_an_outcome_answered_by_an_ending_is_answered():
    c = cc("probe::CC_V0", [], allowed=("SUCCESS", "BACKEND_ERROR"))
    w = wf(nodes({"SUCCESS": "EXIT_DONE", "BACKEND_ERROR": "EXIT_REJECTED"}))
    assert routing_closed([w], context(c, INTENT))["status"] == "PASSED"


def test_an_intent_node_must_answer_every_outcome_its_intent_declares():
    c = cc("probe::CC_V0", [], allowed=("SUCCESS",))
    n = nodes({"SUCCESS": "EXIT_DONE"})
    n["IN_PROBE_V0"]["next"] = {"ACK": "CC_V0"}
    found = routing_closed([wf(n)], context(c, INTENT))["violations"]
    assert len(found) == 1 and "'NACK'" in found[0]["message"], found


def test_a_superseded_workflow_is_not_checked():
    c = cc("probe::CC_V0", [], allowed=("SUCCESS", "BACKEND_ERROR"))
    w = wf(nodes({"SUCCESS": "EXIT_DONE"}), superseded=True)
    result = routing_closed([w], context(c, INTENT))
    assert result["status"] == "PASSED" and result["assert_count"] == 0, result


def test_a_node_no_path_reaches_is_not_checked():
    c = cc("probe::CC_V0", [], allowed=("SUCCESS", "BACKEND_ERROR"))
    n = nodes({"SUCCESS": "EXIT_DONE", "BACKEND_ERROR": "EXIT_REJECTED"})
    n["CC_ORPHAN"] = {"type": "CC", "code": "CC_V0", "next": {"SUCCESS": "EXIT_DONE"}}
    assert routing_closed([wf(n)], context(c, INTENT))["status"] == "PASSED"


def test_a_check_without_precomputed_routing_refuses():
    result = checked_routing_closed([], {})
    assert result["status"] == "FAILED" and "wf_routing" in result["violations"][0]["message"], result


def test_a_contract_from_the_imported_surface_is_read_there():
    c = cc("platform::CC_SHARED_V0", [], allowed=("SUCCESS", "VIOLATION"))
    n = nodes({})
    n["CC_V0"] = {"type": "CC", "code": "platform::CC_SHARED_V0", "next": {"SUCCESS": "EXIT_DONE"}}
    found = routing_closed([wf(n)], context(INTENT, imported={c["fqdn_id"]: c["frontmatter"]}))
    assert len(found["violations"]) == 1 and "'VIOLATION'" in found["violations"][0]["message"], found


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
