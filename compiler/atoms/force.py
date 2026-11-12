"""force.py — whether an artifact is in force.

`artifact::INVARIANT_SUPERSEDED_NOT_IN_FORCE_V0` separates two things supersession once conflated:
an artifact is **present** when it is compiled, and **in force** when it confers effect. A
superseded artifact stays present: compiled, readable and reachable by inspection, so the relation
can be read. It is not in force: not enforced, not dispatchable, not a selection candidate.

The relation is declared once, on the successor, as `supersedes` (`4e` SU-3). A predecessor says
nothing about its own retirement, so whether an artifact is superseded is a fact about the
composition, not about the artifact: it is superseded when some artifact present names it.
`superseded` derives that set once from the artifacts a path already holds, and `in_force` asks it.

Stated once, here, and asked by every path on which presence would otherwise confer effect:
selection at S1, assertion derivation at S4, and dispatch entry and admission. A predicate copied to
each call site is a place per site to forget it. S8 checks what the build produced against it, so
a new path that does not ask is a failed build rather than a superseded artifact quietly in force.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def predecessors(frontmatter: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The identities an artifact declares it supersedes, as full names.

    `supersedes` may name one identity or a list, and both are the same declaration. A bare code is
    read in the successor's own namespace, which is the only place a bare code can mean anything.
    """
    block = frontmatter or {}
    value = block.get("supersedes")
    if not value:
        return ()
    names = [value] if isinstance(value, str) else list(value)
    own = str(block.get("fqdn") or "")
    namespace = own.split("::")[0] if "::" in own else ""
    return tuple(str(n) if "::" in str(n) or not namespace else f"{namespace}::{n}" for n in names)


def superseded(frontmatters: Iterable[Mapping[str, Any] | None]) -> frozenset[str]:
    """Every identity some artifact among these names as its predecessor."""
    return frozenset(name for fm in frontmatters for name in predecessors(fm))


def in_force(fqdn: str, retired: frozenset[str]) -> bool:
    """True unless an artifact in the composition supersedes this one."""
    return fqdn not in retired


def superseded_in(artifacts: Iterable[Mapping[str, Any]], compilation_context: Mapping[str, Any]) -> frozenset[str]:
    """The superseded set a handler sees: its own artifacts and the platform surface it imports."""
    imported = (compilation_context or {}).get("imported_frontmatter") or {}
    return superseded([a.get("frontmatter") for a in artifacts] + list(imported.values()))
