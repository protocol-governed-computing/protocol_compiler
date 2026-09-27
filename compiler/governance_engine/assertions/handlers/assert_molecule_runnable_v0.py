"""
ASSERT_MOLECULE_RUNNABLE_V0 Handler

Every molecule in a composition can be run: each step and loop body resolves to a transform the
runtime can run, the molecule emits a step it declares, and no molecule reaches itself. A molecule
that cannot run is a declaration nothing can keep, and one reaching itself is repetition with no
stated bound; both are knowable when the composition is built.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

from compiler.governance_engine.assertions.handlers._transform_index import (
    STEP_KINDS, index, kind, machine, reachable, step_target, steps, transforms,
)

ASSERT = "ASSERT_MOLECULE_RUNNABLE_V0"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    idx = index(artifacts)
    molecules = [ct for ct in transforms(artifacts) if kind(ct) == "molecule"]

    def refuse(code, violation, fix):
        violations.append({"assert": ASSERT, "artifact": code, "violation": violation, "fix": fix})

    for mol in molecules:
        code = mol.get("artifact_code", "UNKNOWN")
        stream = steps(mol)
        emit = machine(mol).get("emit")
        if not stream:
            refuse(code, "declares no atom_stream, so there is nothing to run", "Declare its steps")
            continue
        if not isinstance(emit, dict) or len(emit) != 1:
            refuse(code, "does not emit exactly one value", "Declare emit as one output mapped to a step")

        symbols = set()
        for n, step in enumerate(stream, 1):
            step_kind = step.get("kind")
            if step.get("as"):
                symbols.add(step["as"])
            if step_kind not in STEP_KINDS:
                refuse(code, f"step {n} is of kind {step_kind!r}; a step is an atom, a molecule or a loop",
                       "Declare the step's kind")
                continue
            target_name = step_target(step)
            target = idx.get(target_name)
            want = "atom" if step_kind == "atom" else "molecule"
            if target is None:
                refuse(code, f"step {n} names {target_name!r}, which is not a transform in this composition",
                       "Name a declared transform")
            elif kind(target) != want:
                refuse(code, f"step {n} is a {step_kind} step naming {target_name!r}, a {kind(target)}; "
                             f"it must name a {want}", f"Name a {want}, or change the step's kind")
            if step_kind == "loop" and not step.get("over"):
                refuse(code, f"step {n} is a loop that states no collection to run over",
                       "State the collection the loop runs once per member of")

        if isinstance(emit, dict):
            for out, symbol in emit.items():
                if symbol not in symbols:
                    refuse(code, f"emits {out!r} from {symbol!r}, a step it does not declare",
                           "Emit the symbol of one of its steps")

        if any(t.get("fqdn_id") == mol.get("fqdn_id") for t in reachable(mol, idx)):
            refuse(code, "reaches itself through its steps — repetition with no stated bound",
                   "Remove the step that leads back to this molecule")

    return {"assert_count": len(molecules), "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
