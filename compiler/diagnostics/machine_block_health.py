"""Machine-block health — does the compiler consume the machine-block keys artifacts declare?

A heuristic, post-successful-build diagnostic. For each compiled artifact whose kind is NOT
already closed by schema conformance, it flattens the machine block to leaf keys and checks
whether each leaf name appears as a string literal in the compiler source. A leaf with no
detected consumer is a *candidate* — not proof — of an unconsumed declaration.

Scope rule (principled, not an arbitrary list): the diagnostic applies only to artifact kinds
whose machine-block consumption is NOT already closed by `additionalProperties: false` schema
conformance. For schema-closed kinds an unconsumed key cannot silently survive, so a census
adds only noise.

Severity: WARNING only. It never fails the build, changes runtime behavior, or asserts a
conformance rule. The authoritative rule is the compiler's actual behavior (and, where it
applies, schema closure). A candidate means exactly: "this machine-block key has no detected
compiler consumer" — the source-inspection method cannot prove a key is truly unused.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_LITERAL = re.compile(r"""['"]([A-Za-z_][A-Za-z0-9_]*)['"]""")


@dataclass
class KindReport:
    consumed: set[str] = field(default_factory=set)
    unconsumed: set[str] = field(default_factory=set)


@dataclass
class HealthReport:
    by_kind: dict[str, KindReport] = field(default_factory=dict)

    @property
    def examined(self) -> int:
        return sum(len(k.consumed) + len(k.unconsumed) for k in self.by_kind.values())

    @property
    def candidate_unconsumed(self) -> int:
        return sum(len(k.unconsumed) for k in self.by_kind.values())

    @property
    def has_candidates(self) -> bool:
        return self.candidate_unconsumed > 0


def _source_literals(compiler_src: Path) -> set[str]:
    """Every quoted identifier appearing anywhere in the compiler source (its consumption surface)."""
    out: set[str] = set()
    for py in compiler_src.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        try:
            out.update(_LITERAL.findall(py.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return out


def _declared_fields(fm: Any) -> Iterable[str]:
    """The top-level declared fields of a machine block.

    Deliberately top-level only: the health question is whether the compiler consumes the
    *fields an artifact declares*. A field's internal shape (nested data — layer names, paths,
    enum values) is that field's own business, read structurally rather than by literal key
    name, and flattening into it produces heuristic noise, not signal. (frontmatter is a
    MappingProxyType, so accept any Mapping.)
    """
    if isinstance(fm, Mapping):
        for k in fm.keys():
            yield str(k)


def check(nodes: Iterable[Any], schema_closed_prefixes: set[str], compiler_src: Path) -> HealthReport:
    """Build the health report over compiled graph nodes."""
    literals = _source_literals(compiler_src)
    # Fail safe: a real compiler source has thousands of literals. If the scan finds far fewer,
    # source is not introspectable (e.g. installed without .py) and every field would falsely
    # read as unconsumed — so report nothing rather than a spurious alarm.
    if len(literals) < 200:
        return HealthReport(by_kind={})
    by_kind: dict[str, KindReport] = defaultdict(KindReport)
    for node in nodes:
        code = getattr(node, "artifact_code", "") or ""
        prefix = code.split("_", 1)[0]
        if not prefix or prefix in schema_closed_prefixes:
            continue  # schema-closed kinds are already guaranteed; skip
        # imported artifacts were authored elsewhere — not this build's declaration surface
        if (getattr(node, "metadata", None) or {}).get("imported"):
            continue
        fm = getattr(node, "frontmatter", None) or {}
        for leaf in set(_declared_fields(fm)):
            (by_kind[prefix].consumed if leaf in literals else by_kind[prefix].unconsumed).add(leaf)
    return HealthReport(by_kind=dict(by_kind))


def format_report(report: HealthReport, verbose: bool) -> list[str]:
    """Render the diagnostic. Empty list = print nothing (clean, non-verbose)."""
    if not report.by_kind:
        return []
    if not verbose:
        if not report.has_candidates:
            return []
        n = report.candidate_unconsumed
        return [f"⚠ Machine-block health: {n} candidate unconsumed key(s). "
                f"Run with --verbose for details."]

    lines = ["", "Machine-block health", "─" * 20]
    consumed_total = 0
    for kind in sorted(report.by_kind):
        r = report.by_kind[kind]
        consumed_total += len(r.consumed)
        lines.append(f"Kind: {kind}")
        for k in sorted(r.consumed):
            lines.append(f"  ✓ {k}")
        for k in sorted(r.unconsumed):
            lines.append(f"  ⚠ {k}  (no detected compiler consumer)")
    lines += [
        "",
        "Summary:",
        f"  machine-block keys examined:  {report.examined}",
        f"  candidate consumed:           {consumed_total}",
        f"  candidate unconsumed:         {report.candidate_unconsumed}",
        "",
        "NOTE: census results are heuristic diagnostics. They do not affect compilation",
        "      success, runtime behavior, or conformance. A candidate means only that a",
        "      key has no detected compiler consumer — not that it is unused.",
    ]
    return lines
