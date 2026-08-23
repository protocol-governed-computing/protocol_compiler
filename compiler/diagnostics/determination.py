"""Construction determination records — evidence that a determination was made, including refusals.

`3e` §3.1: for any determination, its evidence must be sufficient to establish which closure applied,
which rules that closure supplied, what each predicate yielded, what the dominant consequence was,
and that the resulting state is what that consequence permitted.

Construction previously produced none. A refused build wrote a diagnostic to stderr and exited 1, so
the determination *this candidate set is inadmissible under this closure* — the exact subject of
`3e` §3.3 — left no checkable record anywhere. Admissions were evidenced by their output; refusals
by nothing, which is EV-3 and EN-12 breached in the direction that matters, since a system recording
what it permitted and not what it refused has a record of its work proceeding rather than of its
governance operating.

**A record is not usable output.** `4a` GC-6 forbids a refused construction producing usable output,
and `1c` AI-8 states the boundary exactly: after refusal the governed state is as though the proposal
had not been made, *"except for the evidence that it was refused."* The realization's own technique
table lists "a failed build writing nothing" as serving AI-8; that technique overshot the property it
served, and this is the correction.

Records are written outside the compiled output tree. Nothing reads them — they are evidence, and
`3e` §3.2 makes evidence output only.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


RECORD_VERSION = "v0"


def _root() -> Path:
    """Where determination records are written — outside the compiled output tree.

    `PGC_SNAPSHOT_ROOT` is set per build by the runners; the compiled projections live under
    `<root>/compiled`, so records sit beside them rather than within them. A record inside the output
    would be output, and GC-6 is about what a refused construction leaves behind.
    """
    root = os.environ.get("PGC_SNAPSHOT_ROOT")
    if not root:
        # No fallback. A relative default would write the record wherever the process happened to be
        # standing — which put it inside the assembled snapshot the first time this ran, where it
        # would have become undeclared content at acceptance. An unlocatable evidence root is a
        # refusal to write, reported, not a guess.
        raise RuntimeError(
            "PGC_SNAPSHOT_ROOT is not set — there is no declared root to write the determination "
            "record to, and a relative default would place evidence by accident."
        )
    return Path(root) / "determinations"


def _closure(state: Any) -> dict[str, Any]:
    """Which closure applied — `3e` §3.1 point 1."""
    meta = dict(getattr(state, "stage_metadata", {}) or {})
    closure = dict(meta.get("governance_closure") or {})
    return {
        # The closure enumerated. `rules_supplied` and `predicate_results` name every governing
        # element that applied and by what invariant identity — that enumeration is what establishes
        # point 1; the hash below is a compact identifier for the same set, present only where a
        # closure was imported. The platform IS the governance surface and imports none, so it
        # carries no hash and its closure is established by the enumeration alone.
        "authorized_namespaces": list(meta.get("authorized_namespaces", []) or []),
        "imported_governance": closure or None,
    }


def _rules_and_predicates(state: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Which rules the closure supplied, and what each predicate yielded — points 2 and 3.

    `assertion_coverage` is what `s4_govern` already records per derived assertion. It is lifted
    rather than recomputed: a second derivation of one fact is two facts.
    """
    coverage = list((getattr(state, "stage_metadata", {}) or {}).get("assertion_coverage", []) or [])
    supplied = sorted({c.get("assert_code", "") for c in coverage if c.get("assert_code")})
    yielded = [
        {
            "rule": c.get("assert_code"),
            "invariant": c.get("fqdn_id"),
            "result": c.get("status"),
            "violations": c.get("violations", 0),
            "imported": c.get("imported", False),
        }
        for c in coverage
    ]
    return supplied, yielded


def write(state: Any, structure: str, consequence: str, failed_at: str | None = None) -> Path | None:
    """Write the determination record for one construction. Returns its path, or None if unwritable.

    `consequence` is ADMITTED or REFUSED. Both are written, and written the same way: EV-3 requires
    refusals evidenced as fully as admissions, and a record shape that differed between them would
    make the two incomparable — which is how a system ends up able to show what it permitted and not
    what it refused.
    """
    supplied, yielded = _rules_and_predicates(state)
    errors = list(getattr(state, "errors", []) or [])
    materialized = list(getattr(state, "materialized_paths", []) or [])

    record = {
        "record_version": RECORD_VERSION,
        "record_type": "construction_determination",
        "consequence": consequence,
        # 1 — which closure applied
        "closure": _closure(state),
        # 2 — which rules that closure supplied
        "rules_supplied": supplied,
        # 3 — what each predicate yielded
        "predicate_results": yielded,
        # what was proposed
        "proposed": {
            "structure": structure,
            "candidates": len(getattr(state, "graph", None).nodes) if getattr(state, "graph", None) else None,
        },
        # 4 — the dominant consequence, and its grounds
        "grounds": [
            {
                "code": getattr(e, "code", None).value if hasattr(getattr(e, "code", None), "value") else str(getattr(e, "code", "")),
                "phase": getattr(e, "phase", None),
                "fqdn_id": getattr(e, "fqdn_id", None),
                "message": getattr(e, "message", ""),
            }
            for e in errors
        ],
        # 5 — that the resulting state is what the consequence permitted
        "resulting_state": {
            "failed_at": failed_at,
            "materialized_count": len(materialized),
            "nothing_proceeded": consequence == "REFUSED" and not materialized,
        },
        # Observational content, declared as such (`3e` §5): it may differ between two determinations
        # over the same inputs and no determination may depend on it.
        "observational": {"determined_at_ns": time.time_ns()},
    }

    try:
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{structure}.{consequence.lower()}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return path
    except (OSError, RuntimeError):
        # Evidence that cannot be written is a finding, not a reason to fail the determination it
        # records — the determination already happened. Surfaced by the caller, never swallowed.
        return None
