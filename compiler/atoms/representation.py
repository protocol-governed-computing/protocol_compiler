"""
What a declaration's parts are: which name another artifact, and which carry no meaning.

The platform declares it once, in `artifact::VOCAB_DECLARATION_REPRESENTATION_V0`. Every place that
finds a reference reads it from here: the record of references S1 builds, the check that nothing
reaches a stood-down artifact, and the check that a reference is written in full. Before it was
declared, four places each kept a list of their own, and they disagreed about what a reference is.

The declaration is read by its exact identity and never searched for (`4c` ID-14). A build that
cannot see it, or sees it stood down, is refused: a record of references taken without it would
be taken from nothing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DECLARATION = "artifact::VOCAB_DECLARATION_REPRESENTATION_V0"

FULL_NAME = re.compile(r"^[a-z_][a-z0-9_]*::[A-Z][A-Z0-9_]*$")

GROUPS = ("documentation", "unordered", "reference", "reference_keyed", "full_name_required",
          "supersession", "sameness_rules")


class RepresentationUnavailable(ValueError):
    """The declaration cannot be read, so no reference can be found."""


@dataclass(frozen=True)
class Representation:
    documentation: frozenset[str]
    unordered: frozenset[str]
    reference: frozenset[str]
    reference_keyed: frozenset[str]
    full_name_required: frozenset[str]
    supersession: frozenset[str]
    sameness_rules: frozenset[str]

    @classmethod
    def from_frontmatter(cls, frontmatter: dict) -> "Representation":
        if frontmatter.get("superseded_by"):
            raise RepresentationUnavailable(
                f"{DECLARATION} is stood down by {frontmatter['superseded_by']}; the compiler reads "
                f"it by exact identity and must be re-pointed to its successor")
        groups = {}
        for group in GROUPS:
            entries = (frontmatter.get(group) or {}).get("entries") if isinstance(
                frontmatter.get(group), dict) else None
            if not entries:
                raise RepresentationUnavailable(f"{DECLARATION} declares no '{group}' entries")
            groups[group] = frozenset(entries)
        return cls(**groups)

    def as_dict(self) -> dict[str, list[str]]:
        return {group: sorted(getattr(self, group)) for group in GROUPS}

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> "Representation":
        return cls(**{group: frozenset(data[group]) for group in GROUPS})

    def references(self, frontmatter: dict, own: str) -> tuple[set[str], list[str]]:
        """The full names a declaration refers to, and where it writes a full name undeclared.

        A full name at or beneath a reference part is a reference, and so is a full-name key of a
        keyed reference part. A supersession part names an artifact without reaching it. The
        artifact's own identity is not a reference. Any other full name is undeclared.
        """
        found: set[str] = set()
        undeclared: list[str] = []

        def walk(value: Any, path: str, under: bool) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in self.supersession:
                        continue
                    if key in self.reference_keyed and isinstance(item, dict):
                        for name, inner in item.items():
                            if isinstance(name, str) and FULL_NAME.match(name) and name != own:
                                found.add(name)
                            walk(inner, f"{path}.{key}.{name}", under)
                        continue
                    walk(item, f"{path}.{key}", under or key in self.reference)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]", under)
            elif isinstance(value, str) and FULL_NAME.match(value.strip()):
                name = value.strip()
                if name == own:
                    return
                if under:
                    found.add(name)
                else:
                    undeclared.append(path.lstrip("."))

        walk(frontmatter, "", False)
        return found, undeclared

    def short_codes(self, frontmatter: dict) -> list[tuple[str, str]]:
        """`(path, value)` for every value of a part that requires a full name and is not one.

        Read where S1 read it: the value of the part itself, or each member of a list.
        """
        out: list[tuple[str, str]] = []

        def walk(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in self.full_name_required:
                        members = item if isinstance(item, list) else [item]
                        out.extend((f"{path}.{key}", m) for m in members
                                   if isinstance(m, str) and "::" not in m)
                    walk(item, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]")

        walk(frontmatter, "")
        return [(p.lstrip("."), v) for p, v in out]


def locate(local: dict[str, dict], build_config: dict) -> Representation:
    """The declaration this build reads: compiled here, or in the platform surface it imports."""
    if DECLARATION in local:
        return Representation.from_frontmatter(local[DECLARATION])
    imp = (build_config.get("artifact_discovery", {}) or {}).get("import_surface", {}) or {}
    if not imp.get("domain"):
        raise RepresentationUnavailable(
            f"{DECLARATION} is not in this build and the build imports no platform surface")
    from compiler.governance_engine.platform_root import platform_root
    canonical = platform_root() / "snapshot" / "compiled" / "canonical"
    for path in sorted(Path(canonical).rglob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(record, dict) and record.get("fqdn_id") == DECLARATION:
            return Representation.from_frontmatter(record.get("frontmatter", {}) or {})
    raise RepresentationUnavailable(
        f"{DECLARATION} is not in the imported platform surface at {canonical}")
