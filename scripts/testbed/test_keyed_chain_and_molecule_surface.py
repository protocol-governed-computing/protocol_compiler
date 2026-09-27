"""
Two refusals the first domain with molecules and a keyed-node chain met, and neither was a defect of
that domain.

A domain's transform surface is closed by derivation, `declared == invoked`, and V0 counted only the
transforms a contract's pipeline names. A molecule's steps are reached through the molecule, so they
were refused as unreached. V1 closes the invoked set over molecule steps, however deep.

Routing was checked for cycles over the contracts places run, not the places, so two places running
one contract in sequence read as a contract depending on itself. Routing is now acyclic per workflow,
over its own node keys; a routing loop is still refused.
"""
import sys
from types import SimpleNamespace

from compiler.governance_engine.assertions.handlers.assert_ct_surface_derived_closed_v1 import execute as closed
from compiler.graph.types import NodeKind
from compiler.stages.s4_govern import _workflows_with_routing_cycles

D = "probe"
OFFER, CHOOSE, PASS, WRITE = (f"{D}::CT_IMPURE_OFFER_V0", f"{D}::CT_PURE_CHOOSE_V0",
                              f"{D}::CT_PASS_V0", f"{D}::CT_WRITE_V0")


def ct(fqdn, stream=None):
    machine = {"atom_stream": stream} if stream else {}
    return {"fqdn_id": fqdn, "frontmatter": {"artifact_kind": "CAPABILITY_TRANSFORM", "machine": machine}}


def cc(fqdn, transforms):
    return {"fqdn_id": fqdn, "frontmatter": {"artifact_kind": "CAPABILITY_CONTRACT",
                                             "core": {"pipeline": [{"transform": t} for t in transforms]}}}


SURFACE = [ct(OFFER), ct(CHOOSE),
           ct(PASS, [{"kind": "atom", "atom": OFFER}, {"kind": "atom", "atom": CHOOSE}]),
           ct(WRITE, [{"kind": "loop", "molecule": PASS}]),
           cc(f"{D}::CC_WRITE_V0", [WRITE])]
CONTEXT = {"is_domain_build": True}


def test_transforms_reached_only_through_a_molecule_are_invoked():
    result = closed(SURFACE, CONTEXT)
    assert result["status"] == "PASSED", result["violations"]


def test_a_transform_no_contract_or_molecule_reaches_is_still_refused():
    result = closed(SURFACE + [ct(f"{D}::CT_PURE_ORPHAN_V0")], CONTEXT)
    assert [v["fqdn"] for v in result["violations"]] == [f"{D}::CT_PURE_ORPHAN_V0"], result


def workflow(nodes):
    return SimpleNamespace(nodes={f"{D}::WF_V0": SimpleNamespace(
        kind=NodeKind.WF, frontmatter={"core": {"nodes": nodes}})})


def test_two_places_running_one_contract_in_sequence_are_not_a_cycle():
    graph = workflow({
        "CHECK_STOPPED": {"type": "CC", "code": "CC_RELEASE_V0", "next": {"SUCCESS": "CHECK_FINISHED"}},
        "CHECK_FINISHED": {"type": "CC", "code": "CC_RELEASE_V0", "next": {"SUCCESS": "EXIT_OK"}},
        "EXIT_OK": {"type": "EXIT"},
    })
    assert _workflows_with_routing_cycles(graph) == []


def test_routing_that_returns_to_a_node_it_left_is_a_cycle():
    graph = workflow({
        "A": {"type": "CC", "code": "CC_A_V0", "next": {"SUCCESS": "B"}},
        "B": {"type": "CC", "code": "CC_B_V0", "next": {"SUCCESS": "A"}},
    })
    assert _workflows_with_routing_cycles(graph) == [f"{D}::WF_V0"]


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
