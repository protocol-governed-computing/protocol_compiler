"""
Molecule composition — the compiler's half of software_governance/dossiers/molecule_composition.

Each refusal the four assertions declare is shown to fire on a composition built to trip it, and to
stay silent on one that keeps the rule: a check that has only ever been seen green has not been seen
to check anything. The lowering is shown to seal a loop whose body is a molecule, with every atom
carrying its implementation and every step its declared purity, so the runtime resolves nothing.
"""

import sys
from types import SimpleNamespace

from compiler.governance_engine.assertions.handlers.assert_ct_governed_by_kind_v0 import execute as governed_by_kind
from compiler.governance_engine.assertions.handlers.assert_molecule_runnable_v0 import execute as runnable
from compiler.governance_engine.assertions.handlers.assert_molecule_purity_consistent_v0 import execute as purity_consistent
from compiler.governance_engine.assertions.handlers.assert_nondeterminism_not_routed_v0 import execute as not_routed

s5 = sys.modules["compiler.stages.s5_construct"] if "compiler.stages.s5_construct" in sys.modules else None
if s5 is None:
    import importlib
    s5 = importlib.import_module("compiler.stages.s5_construct")

DET = "capability_transforms::CONSTITUTION_DETERMINISTIC_ATOMS_V0"
MOL = "capability_transforms::CONSTITUTION_MOLECULES_V0"
NDA = "capability_transforms::CONSTITUTION_NONDETERMINISTIC_ATOMS_V0"
NS = "probe"


def atom(code, purity="ct_pure", governed_by=None):
    gov = governed_by or (NDA if purity == "ct_impure" else DET)
    return {"artifact_type": "CT", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"governed_by": gov, "machine": {
                "ct_kind": "atom", "ct_purity": purity,
                "implementation": {"module": f"probe.{code.lower()}", "callable": "execute"}}}}


def molecule(code, stream, emit, purity="ct_pure", governed_by=MOL):
    return {"artifact_type": "CT", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"governed_by": governed_by, "machine": {
                "ct_kind": "molecule", "ct_purity": purity, "atom_stream": stream, "emit": emit}}}


def contract(code, transforms):
    return {"artifact_type": "CC", "artifact_code": code, "fqdn_id": f"{NS}::{code}",
            "frontmatter": {"core": {"pipeline": [{"step": f"s{i}", "transform": t}
                                                  for i, t in enumerate(transforms)]}}}


# The shape the concept needs: a loop whose body is a molecule of an offering atom that is not
# deterministic and a choosing atom that is; the loop emits the chooser's result.
OFFER = atom("CT_IMPURE_OFFER_V0", "ct_impure")
CHOOSE = atom("CT_PURE_CHOOSE_V0")
PASS = molecule("CT_PASS_V0", [
    {"kind": "atom", "atom": f"{NS}::CT_IMPURE_OFFER_V0", "as": "offered"},
    {"kind": "atom", "atom": f"{NS}::CT_PURE_CHOOSE_V0", "as": "chosen"},
], {"result": "chosen"}, purity="ct_impure")
WRITE = molecule("CT_WRITE_V0", [
    {"kind": "loop", "molecule": f"{NS}::CT_PASS_V0", "as": "written",
     "over": "$.inputs.positions", "iterator": "position"},
], {"result": "written"}, purity="ct_impure")
GOOD = [OFFER, CHOOSE, PASS, WRITE]


def violations(handler, artifacts):
    return handler(artifacts, {})["violations"]


def test_a_well_formed_composition_passes_every_check():
    for handler in (governed_by_kind, runnable, purity_consistent, not_routed):
        assert violations(handler, GOOD) == [], handler.__module__


def test_placement_follows_kind_and_purity():
    wrong = atom("CT_IMPURE_X_V0", "ct_impure", governed_by=DET)
    assert len(violations(governed_by_kind, [wrong])) == 1
    mol_wrong = molecule("CT_M_V0", PASS["frontmatter"]["machine"]["atom_stream"], {"r": "chosen"},
                         governed_by=DET)
    assert len(violations(governed_by_kind, [OFFER, CHOOSE, mol_wrong])) == 1
    undeclared = atom("CT_U_V0", "")
    assert len(violations(governed_by_kind, [undeclared])) == 1


def test_an_unrunnable_molecule_is_refused():
    missing = molecule("CT_M_V0", [{"kind": "atom", "atom": f"{NS}::CT_ABSENT_V0", "as": "x"}], {"r": "x"})
    assert any("not a transform" in v["violation"] for v in violations(runnable, [missing]))
    kind_mismatch = molecule("CT_M_V0", [{"kind": "loop", "molecule": f"{NS}::CT_PURE_CHOOSE_V0",
                                          "as": "x", "over": "$.inputs.p"}], {"r": "x"})
    assert any("must name a molecule" in v["violation"] for v in violations(runnable, [CHOOSE, kind_mismatch]))
    no_collection = molecule("CT_M_V0", [{"kind": "loop", "molecule": f"{NS}::CT_PASS_V0", "as": "x"}],
                             {"r": "x"})
    assert any("no collection" in v["violation"] for v in violations(runnable, GOOD + [no_collection]))
    bad_emit = molecule("CT_M_V0", [{"kind": "atom", "atom": f"{NS}::CT_PURE_CHOOSE_V0", "as": "x"}],
                        {"r": "y"})
    assert any("does not declare" in v["violation"] for v in violations(runnable, [CHOOSE, bad_emit]))


def test_a_molecule_containing_itself_is_refused():
    a = molecule("CT_A_V0", [{"kind": "molecule", "molecule": f"{NS}::CT_B_V0", "as": "b"}], {"r": "b"})
    b = molecule("CT_B_V0", [{"kind": "molecule", "molecule": f"{NS}::CT_A_V0", "as": "a"}], {"r": "a"})
    found = violations(runnable, [a, b])
    assert sum("reaches itself" in v["violation"] for v in found) == 2


def test_a_molecule_claiming_determinism_over_a_nondeterministic_step_is_refused():
    claims_pure = molecule("CT_PASS_V0", PASS["frontmatter"]["machine"]["atom_stream"],
                           {"result": "chosen"}, purity="ct_pure")
    assert len(violations(purity_consistent, [OFFER, CHOOSE, claims_pure])) == 1
    assert violations(purity_consistent, GOOD) == []


def test_nothing_routes_on_a_nondeterministic_result():
    direct = contract("CC_DIRECT_V0", [f"{NS}::CT_IMPURE_OFFER_V0"])
    assert len(violations(not_routed, [OFFER, direct])) == 1
    through_molecule = contract("CC_WRITE_V0", [f"{NS}::CT_WRITE_V0"])
    assert violations(not_routed, GOOD + [through_molecule]) == []
    emits_offer = molecule("CT_PASS_V0", PASS["frontmatter"]["machine"]["atom_stream"],
                           {"result": "offered"}, purity="ct_impure")
    assert len(violations(not_routed, [OFFER, CHOOSE, emits_offer])) == 1


def _node(artifact):
    return SimpleNamespace(fqdn=artifact["fqdn_id"], artifact_code=artifact["artifact_code"],
                           frontmatter={**artifact["frontmatter"], "core": {"inputs": {}}})


def test_a_loop_over_a_molecule_is_sealed_whole():
    index = {a["artifact_code"]: _node(a) for a in GOOD}
    errors = []
    sealed = s5._lower_molecule(index["CT_WRITE_V0"], index, errors, depth=0)
    assert errors == [], errors
    assert sealed["outputs"] == {"result": {"from": "written"}}
    (loop,) = sealed["atom_stream"]
    assert loop["loop"]["over"] == "$.inputs.positions"
    assert loop["purity"] == "ct_impure"
    offer, choose = loop["molecule"]["atom_stream"]
    assert offer["handler_ref"] == {"module": "probe.ct_impure_offer_v0", "callable": "execute"}
    assert (offer["purity"], choose["purity"]) == ("ct_impure", "ct_pure")
    assert loop["molecule"]["outputs"] == {"result": {"from": "chosen"}}


def test_an_atom_run_directly_is_sealed_with_its_purity():
    # Sealed without it, a contract running a non-deterministic atom directly had the atom's
    # results neither recorded nor substituted on replay: the sealed step alone decides that.
    for artifact, purity in ((OFFER, "ct_impure"), (CHOOSE, "ct_pure")):
        ir, errors = s5._build_ct_ir(_node(artifact), {})
        assert errors == [], errors
        (step,) = ir["atom_stream"]
        assert step["purity"] == purity, step


def test_an_unresolved_step_is_a_lowering_error():
    index = {"CT_M_V0": _node(molecule("CT_M_V0", [{"kind": "atom", "atom": f"{NS}::CT_ABSENT_V0",
                                                   "as": "x"}], {"r": "x"}))}
    errors = []
    s5._lower_molecule(index["CT_M_V0"], index, errors, depth=0)
    assert len(errors) == 1 and "Unresolved" in errors[0].message


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
