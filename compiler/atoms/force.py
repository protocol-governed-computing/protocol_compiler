"""force.py — whether an artifact is in force.

`artifact::INVARIANT_SUPERSEDED_NOT_IN_FORCE_V0` separates two things supersession once conflated:
an artifact is **present** when it is compiled, and **in force** when it confers effect. A
superseded artifact stays present: compiled, readable and reachable by inspection, so the relation
it declares can be read. It is not in force: not enforced, not dispatchable, not a selection
candidate.

Stated once, here, and asked by every path on which presence would otherwise confer effect:
selection at S1, assertion derivation at S4, and dispatch entry and admission. A predicate copied to
each call site is a place per site to forget it. S8 checks what the build produced against it, so
a new path that does not ask is a failed build rather than a superseded artifact quietly in force.
"""
from __future__ import annotations

from typing import Any, Mapping


def in_force(frontmatter: Mapping[str, Any] | None) -> bool:
    """True unless the artifact declares a successor."""
    return not (frontmatter or {}).get("superseded_by")
