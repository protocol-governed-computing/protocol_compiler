"""
The sealed dispatch realizes every transition a workflow declares, at the node that declares it.

Routing, endings and announcements were indexed by the contract a node runs. A contract run at
several places kept the last place's continuation: a causal language model's submission ended every
record node where the last did and announced nothing, and two ai_governance workflows carried the
same collision unnoticed. Every phase check passed — they read the declarations, which were right.
S8 now reads the sealed tables against the declarations and refuses the build where they differ.
"""
import sys
from types import SimpleNamespace

from compiler.graph.types import NodeKind
from compiler.stages.s8_verify import _verify_dispatch_routing

WF = 90
SUCCESS, VIOLATION = 601, 602

# One contract, CC_CONFIRM_V0, at two places; one contract, CC_RECORD_V0, at three.
NODES = {
    "CONFIRM_STOPPED": {"type": "CC", "code": "CC_CONFIRM_V0",
                        "next": {"SUCCESS": "CONFIRM_FINISHED", "VIOLATION": "RECORD_BY_RULE"}},
    "CONFIRM_FINISHED": {"type": "CC", "code": "CC_CONFIRM_V0",
                         "next": {"SUCCESS": "RECORD_RESPONDED", "VIOLATION": "RECORD_UNFINISHED"}},
    "RECORD_RESPONDED": {"type": "CC", "code": "CC_RECORD_V0", "next": {"SUCCESS": "EXIT_RESPONDED"}},
    "RECORD_BY_RULE": {"type": "CC", "code": "CC_RECORD_V0", "next": {"SUCCESS": "EXIT_REFUSED"}},
    "RECORD_UNFINISHED": {"type": "CC", "code": "CC_RECORD_V0", "next": {"SUCCESS": "EXIT_REFUSED"}},
    "EXIT_RESPONDED": {"type": "EXIT", "emit": "probe::EV_RESPONDED_V0"},
    "EXIT_REFUSED": {"type": "EXIT", "emit": "probe::EV_REFUSED_V0"},
}

GRAPH = SimpleNamespace(
    nodes={"probe::WF_V0": SimpleNamespace(kind=NodeKind.WF, address=WF,
                                           frontmatter={"core": {"nodes": NODES}})},
    address_table={"transition::SUCCESS": SUCCESS, "transition::VIOLATION": VIOLATION},
)


def step(key):
    return {"addr": 1, "key": key}


def ending(exit_key):
    return {"exit": exit_key, "type": "EXIT"}


def faithful():
    """The dispatch the compiler seals for NODES, keyed by node."""
    s, v = str(SUCCESS), str(VIOLATION)
    return {
        "routing": {str(WF): {
            "CONFIRM_STOPPED": {s: step("CONFIRM_FINISHED"), v: step("RECORD_BY_RULE")},
            "CONFIRM_FINISHED": {s: step("RECORD_RESPONDED"), v: step("RECORD_UNFINISHED")},
        }},
        "terminal": {str(WF): {
            "RECORD_RESPONDED": {s: ending("EXIT_RESPONDED")},
            "RECORD_BY_RULE": {s: ending("EXIT_REFUSED")},
            "RECORD_UNFINISHED": {s: ending("EXIT_REFUSED")},
        }},
        "emits": {str(WF): {
            "RECORD_RESPONDED": {"SUCCESS": ["probe::EV_RESPONDED_V0"]},
            "RECORD_BY_RULE": {"SUCCESS": ["probe::EV_REFUSED_V0"]},
            "RECORD_UNFINISHED": {"SUCCESS": ["probe::EV_REFUSED_V0"]},
        }},
    }


def refusals(content):
    return [e.message for e in _verify_dispatch_routing(content, GRAPH)]


def test_a_faithful_dispatch_passes():
    assert refusals(faithful()) == []


def test_a_place_that_took_another_places_continuation_is_refused():
    content = faithful()
    # What contract keying sealed: the second confirmation's refusal stood for the first's.
    content["routing"][str(WF)]["CONFIRM_STOPPED"][str(VIOLATION)] = step("RECORD_UNFINISHED")
    found = refusals(content)
    assert len(found) == 1 and "CONFIRM_STOPPED" in found[0] and "RECORD_BY_RULE" in found[0], found


def test_an_ending_that_announces_nothing_it_declared_is_refused():
    content = faithful()
    del content["emits"][str(WF)]["RECORD_RESPONDED"]
    content["terminal"][str(WF)]["RECORD_RESPONDED"][str(SUCCESS)] = ending("EXIT_REFUSED")
    found = refusals(content)
    assert len(found) == 2 and all("RECORD_RESPONDED" in m for m in found), found


def test_a_dispatch_keyed_by_contract_is_refused():
    s, v = str(SUCCESS), str(VIOLATION)
    content = {
        "routing": {str(WF): {"10": {s: step("RECORD_RESPONDED"), v: step("RECORD_UNFINISHED")}}},
        "terminal": {str(WF): {"20": {s: ending("EXIT_REJECTED")}}},
        "emits": {},
    }
    found = refusals(content)
    assert any("answers to no declared transition" in m for m in found), found
    assert any("CONFIRM_STOPPED" in m for m in found), found


def test_an_outcome_with_no_address_is_refused_rather_than_dropped():
    nodes = dict(NODES, RECORD_RESPONDED={"type": "CC", "code": "CC_RECORD_V0",
                                          "next": {"SUCCESS": "EXIT_RESPONDED",
                                                   "UNHEARD_OF": "EXIT_REFUSED"}})
    graph = SimpleNamespace(nodes={"probe::WF_V0": SimpleNamespace(
        kind=NodeKind.WF, address=WF, frontmatter={"core": {"nodes": nodes}})},
        address_table=GRAPH.address_table)
    found = [e.message for e in _verify_dispatch_routing(faithful(), graph)]
    assert len(found) == 1 and "UNHEARD_OF" in found[0] and "no address" in found[0], found


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
