"""
One declaration says what a reference is, and every place that finds one reads it.

The record of references read a fixed list of nine parts, the reach check read every value, the
FQDN-only check kept a list of four, and nothing compared two declarations at all. The platform now
declares the parts in `artifact::VOCAB_DECLARATION_REPRESENTATION_V1`: the reference parts, the
keyed ones, the ones that require a full name, and the ones that declare supersession. S1 records
from it and refuses a full name written anywhere else; both reference checks read it.
"""
import re
import sys
from pathlib import Path

import yaml

from compiler.atoms.representation import (
    DECLARATION, Representation, RepresentationUnavailable, locate)
from compiler.governance_engine.assertions.handlers.assert_fqdn_only_references_v0 import (
    execute as fqdn_only)
from compiler.governance_engine.assertions.handlers.assert_superseded_not_referenced_v0 import (
    execute as not_referenced)

WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = (WORKSPACE / "software_governance" / "registry" / "artifact" / "vocabulary"
          / "VOCAB_DECLARATION_REPRESENTATION_V1.md")


def declared() -> dict:
    return yaml.safe_load(re.search(r"```yaml\n(.*?)```", SOURCE.read_text(), re.S).group(1))


REP = Representation.from_frontmatter(declared())


def artifact(fqdn, kind="CC", **frontmatter):
    return {"fqdn_id": fqdn, "artifact_type": kind, "artifact_code": fqdn.split("::")[-1],
            "frontmatter": {"fqdn": fqdn, **frontmatter}}


# --- the declaration ---------------------------------------------------------------------------

def test_the_declaration_names_both_rules_a_comparison_applies():
    assert REP.sameness_rules == {"explanation_only_as_text", "reference_to_declared_successor"}


def test_a_stood_down_declaration_is_refused():
    try:
        Representation.from_frontmatter({**declared(), "superseded_by": ["artifact::X_V2"]})
    except RepresentationUnavailable as exc:
        assert "re-pointed" in str(exc)
    else:
        raise AssertionError("a stood-down declaration was read")


def test_a_declaration_missing_a_group_is_refused():
    fm = declared()
    fm.pop("supersession")
    try:
        Representation.from_frontmatter(fm)
    except RepresentationUnavailable as exc:
        assert "supersession" in str(exc)
    else:
        raise AssertionError("a declaration without its supersession parts was read")


def test_a_build_that_cannot_see_the_declaration_is_refused():
    try:
        locate({}, {"artifact_discovery": {}})
    except RepresentationUnavailable as exc:
        assert DECLARATION in str(exc)
    else:
        raise AssertionError("a build without the declaration found references")


# --- the record of references ------------------------------------------------------------------

def test_a_full_name_in_a_reference_part_is_recorded_wherever_it_sits():
    fm = {"enforced_by": "conformance::CONSTITUTION_ASSERT_V0",
          "core": {"nodes": {"EXIT_DONE": {"emit": ["probe::EV_DONE_V0"]}},
                   "inputs": {"phase_workflows": {"p0": "probe::WF_P0_V0"}}}}
    found, undeclared = REP.references(fm, "probe::WF_PROBE_V0")
    assert found == {"conformance::CONSTITUTION_ASSERT_V0", "probe::EV_DONE_V0",
                     "probe::WF_P0_V0"} and not undeclared, (found, undeclared)


def test_a_full_name_outside_every_declared_part_is_undeclared():
    found, undeclared = REP.references({"core": {"note": "probe::CT_X_V0"}}, "probe::CC_V0")
    assert not found and undeclared == ["core.note"], (found, undeclared)


def test_supersession_names_without_reaching_and_the_own_identity_is_not_a_reference():
    fm = {"fqdn": "probe::CC_V1", "supersedes": "probe::CC_V0", "superseded_by": ["probe::CC_V2"]}
    assert REP.references(fm, "probe::CC_V1") == (set(), [])


def test_full_name_keys_of_a_binding_are_references_and_field_names_are_not():
    fm = {"core": {"bindings": {"capability_side_effects::CS_REGISTRY_V0": {
        "policy": {"structure": "probe::STRUCTURE_STORE_V0"}}}},
          "cases": [{"bindings": {"timestamp": 1}}]}
    found, undeclared = REP.references(fm, "probe::RB_V0")
    assert found == {"capability_side_effects::CS_REGISTRY_V0", "probe::STRUCTURE_STORE_V0"} \
        and not undeclared, (found, undeclared)


# --- a short code where a full name is required -------------------------------------------------

def test_a_short_code_in_a_part_requiring_a_full_name_is_refused():
    a = artifact("probe::WF_V0", governed_by="CONSTITUTION_WORKFLOW_V0")
    found = fqdn_only([a], {"representation": REP})["violations"]
    assert len(found) == 1 and "CONSTITUTION_WORKFLOW_V0" in found[0]["message"], found


def test_binding_keys_are_not_held_to_a_full_name():
    # A workflow's admission keys its bindings by short code, as its requires and forbids do, and a
    # test case keys them by field name. Short-code references are parked; none is refused here.
    wf = artifact("probe::WF_V0", kind="WF", core={"admission": {"bindings": {"EV_DONE_V0": {}}}},
                  cases=[{"bindings": {"timestamp": 1}}])
    assert fqdn_only([wf], {"representation": REP})["status"] == "PASSED"


def test_a_reference_check_without_the_declaration_refuses():
    for check in (fqdn_only, not_referenced):
        result = check([], {})
        assert result["status"] == "FAILED" and "representation" in \
            result["violations"][0]["message"], result


# --- nothing reaches a stood-down artifact ------------------------------------------------------

RETIRED = artifact("probe::CC_OLD_V0", superseded_by=["probe::CC_NEW_V0"])
SUCCESSOR = artifact("probe::CC_NEW_V0", supersedes="probe::CC_OLD_V0")


def test_a_full_name_reaching_a_stood_down_artifact_is_refused():
    wf = artifact("probe::WF_V0", kind="WF", core={"nodes": {"N": {"fqdn_id": "probe::CC_OLD_V0"}}})
    found = not_referenced([RETIRED, SUCCESSOR, wf], {"representation": REP})["violations"]
    assert len(found) == 1 and found[0]["fqdn"] == "probe::WF_V0", found


def test_a_short_code_reaching_a_stood_down_artifact_is_still_refused():
    intent = artifact("probe::IN_V0", kind="IN", core={"workflow": "CC_OLD_V0"})
    found = not_referenced([RETIRED, SUCCESSOR, intent], {"representation": REP})["violations"]
    assert len(found) == 1 and found[0]["fqdn"] == "probe::IN_V0", found


def test_a_place_label_is_not_a_reach_and_a_stale_code_is():
    # Re-pointed: the place keeps its label and the route to it; its code names the successor.
    nodes = {"CC_OLD_V0": {"type": "CC", "code": "CC_NEW_V0", "next": {"SUCCESS": "EXIT_DONE"}},
             "IN_V0": {"type": "IN", "next": {"ACK": "CC_OLD_V0"}}}
    wf = artifact("probe::WF_V0", kind="WF", core={"nodes": nodes})
    assert not_referenced([RETIRED, SUCCESSOR, wf], {"representation": REP})["status"] == "PASSED"
    stale = artifact("probe::WF_V0", kind="WF", core={"nodes": {
        "CC_OLD_V0": {"type": "CC", "code": "CC_OLD_V0", "next": {"SUCCESS": "EXIT_DONE"}}}})
    found = not_referenced([RETIRED, SUCCESSOR, stale], {"representation": REP})["violations"]
    assert len(found) == 1 and found[0]["fqdn"] == "probe::WF_V0", found


def test_naming_what_you_stand_in_for_is_not_a_reach():
    assert not_referenced([RETIRED, SUCCESSOR], {"representation": REP})["status"] == "PASSED"


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
