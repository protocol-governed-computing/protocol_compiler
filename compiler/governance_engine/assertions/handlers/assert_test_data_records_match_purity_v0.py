"""
ASSERT_TEST_DATA_RECORDS_MATCH_PURITY_V0 Handler

A case supplies a recorded result for exactly the non-deterministic steps of what it tests. A result
supplied for a deterministic step asserts a replay that never happens; a non-deterministic step left
without one would run, and the case's expected result could not be exact.

A recorded result is addressed by the path the runtime gives a step inside a molecule:
`written[3]/offered` is the step `offered` on the fourth pass of the loop `written`. Each segment is
checked against the molecule's declared steps — a pass index only on a loop, the last segment an atom
declared `ct_impure`. How many passes a loop runs depends on the case's own bindings, so that every
pass is covered is confirmed when the case runs: the executor refuses a non-deterministic step with no
record, and the runner refuses a record nothing used.

CONSTITUTIONAL: Pure rule checker - reads pre-computed structure from context
"""

import re

from compiler.governance_engine.assertions.handlers._test_data import cases, target, vectors
from compiler.governance_engine.assertions.handlers._transform_index import (
    NONDETERMINISTIC_PURITY, index, kind, purity, reachable, step_target, steps,
)

ASSERT = "ASSERT_TEST_DATA_RECORDS_MATCH_PURITY_V0"
_SEGMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")


def _path_problem(path: str, molecule: dict, idx: dict) -> str | None:
    """Why a recorded path names no non-deterministic step of this molecule, or None when it does."""
    current = molecule
    segments = path.split("/")
    for i, segment in enumerate(segments):
        m = _SEGMENT.match(segment)
        if not m:
            return f"segment {segment!r} is not a step symbol with an optional pass index"
        symbol, pass_index = m.group(1), m.group(2)
        step = next((s for s in steps(current) if s.get("as") == symbol), None)
        if step is None:
            return f"{current.get('artifact_code')} has no step {symbol!r}"
        if pass_index is not None and step.get("kind") != "loop":
            return f"step {symbol!r} is not a loop and has no passes"
        if step.get("kind") == "loop" and pass_index is None:
            return f"step {symbol!r} is a loop; a path through it names the pass"
        stepped = idx.get(step_target(step))
        if stepped is None:
            return f"step {symbol!r} runs nothing this composition declares"
        last = i == len(segments) - 1
        if last:
            if kind(stepped) != "atom":
                return f"step {symbol!r} is a molecule; a result is recorded for an atom"
            if purity(stepped) != NONDETERMINISTIC_PURITY:
                return f"step {symbol!r} runs {stepped.get('artifact_code')}, which is deterministic"
            return None
        if kind(stepped) != "molecule":
            return f"step {symbol!r} is an atom and has no steps beneath it"
        current = stepped
    return "path is empty"


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []
    idx = index(artifacts)
    checked = 0

    def refuse(vector, case, message):
        violations.append({
            "assert": ASSERT, "artifact": vector.get("artifact_code", "UNKNOWN"),
            "violation": f"case {case.get('case_id')!r}: {message}",
            "fix": "Supply a recorded result for exactly the non-deterministic steps the target runs",
        })

    for vector in vectors(artifacts):
        tested = idx.get(target(vector))
        if tested is None:
            continue  # an unresolved target is the reference checks' finding, not this one's
        impure_symbols = set()
        if kind(tested) == "molecule":
            impure = {t.get("fqdn_id") for t in reachable(tested, idx) if purity(t) == NONDETERMINISTIC_PURITY}
            stack = [tested]
            seen = set()
            while stack:
                current = stack.pop()
                for s in steps(current):
                    t = idx.get(step_target(s))
                    if t is None:
                        continue
                    if t.get("fqdn_id") in impure and kind(t) == "atom":
                        impure_symbols.add(s.get("as"))
                    if kind(t) == "molecule" and t.get("fqdn_id") not in seen:
                        seen.add(t.get("fqdn_id"))
                        stack.append(t)
        for case in cases(vector):
            checked += 1
            recorded = case.get("recorded") or {}
            if kind(tested) != "molecule":
                if recorded:
                    refuse(vector, case, f"supplies recorded results for {tested.get('artifact_code')}, "
                                         f"an atom; an atom is run, never replayed")
                continue
            for path in recorded:
                problem = _path_problem(path, tested, idx)
                if problem:
                    refuse(vector, case, f"recorded path {path!r}: {problem}")
            covered = {p.split("/")[-1].split("[")[0] for p in recorded}
            for symbol in sorted(impure_symbols - covered):
                refuse(vector, case, f"supplies no recorded result for the non-deterministic step "
                                     f"{symbol!r}, which would then run")
    return {"assert_count": checked, "violations": violations,
            "status": "FAILED" if violations else "PASSED"}
