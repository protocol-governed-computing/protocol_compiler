"""Machine-block key census — which authored keys does the compiler actually read?

Scans every ``## Machine`` block reachable from the registry roots, flattens the
YAML into dotted key paths, then greps the compiler source for each leaf key
name. A key nobody names in source is a candidate dead definition.

Usage:
    python scripts/machine_key_census.py [--roots PATH ...] [--src PATH ...]
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

MACHINE_BLOCK = re.compile(
    r"^## Machine\s*\n+```yaml\s*\n(?P<y>.*?)\n```", re.MULTILINE | re.DOTALL
)

WORKSPACE = Path(__file__).resolve().parents[2]

DEFAULT_ROOTS = [
    WORKSPACE / "software_governance" / "registry",
    WORKSPACE / "standards",
    WORKSPACE / "software_governance" / "domains",
]

DEFAULT_SRC = [
    WORKSPACE / "protocol_compiler" / "compiler",
    WORKSPACE / "snapshot_assembler",
    WORKSPACE / "protocol_runtime",
]


def machine_blocks(roots: Iterable[Path]) -> Iterable[tuple[Path, dict]]:
    for root in roots:
        if not root.is_dir():
            continue
        for md in sorted(root.rglob("*.md")):
            m = MACHINE_BLOCK.search(md.read_text(encoding="utf-8"))
            if not m:
                continue
            try:
                data = yaml.safe_load(m.group("y").rstrip())
            except yaml.YAMLError:
                continue
            if isinstance(data, dict):
                yield md, data


def flatten(data: Any, prefix: str = "") -> Iterable[str]:
    """Dotted key paths; list elements collapse to a single ``[]`` segment."""
    if isinstance(data, dict):
        for k, v in data.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            yield path
            yield from flatten(v, path)
    elif isinstance(data, list):
        for item in data:
            yield from flatten(item, f"{prefix}[]")


def source_tokens(srcs: Iterable[Path]) -> tuple[set[str], set[str]]:
    """(quoted string literals, bare identifiers) appearing in consumer source.

    A dict key can only be read via a string literal (``fm["k"]``, ``.get("k")``,
    ``"k" in fm``) or a f-string/format path. Bare-identifier-only matches are
    coincidence (a local variable named the same) and are reported separately.
    """
    literals: set[str] = set()
    idents: set[str] = set()
    lit = re.compile(r"""['"]([A-Za-z_][A-Za-z0-9_]*)['"]""")
    word = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    for src in srcs:
        if not src.is_dir():
            continue
        for py in src.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            text = py.read_text(encoding="utf-8", errors="ignore")
            literals.update(lit.findall(text))
            idents.update(word.findall(text))
    return literals, idents


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="*", type=Path, default=DEFAULT_ROOTS)
    ap.add_argument("--src", nargs="*", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--kind", help="restrict output to one artifact_kind (e.g. INVARIANT)")
    args = ap.parse_args()

    literals, idents = source_tokens(args.src)

    # key path -> {artifact_kind: count}
    paths: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for _path, data in machine_blocks(args.roots):
        kind = str(data.get("artifact_kind") or "UNKNOWN")
        for p in set(flatten(data)):
            paths[p][kind] += 1

    def leaf(path: str) -> str:
        return path.rsplit(".", 1)[-1].replace("[]", "")

    read, weak, dead = [], [], []
    for p in sorted(paths):
        name = leaf(p)
        if name in literals:
            read.append(p)
        elif name in idents:
            weak.append(p)
        else:
            dead.append(p)

    kind_filter = args.kind

    def emit(title: str, rows: list[str]) -> None:
        rows = [p for p in rows if not kind_filter or kind_filter in paths[p]]
        print(f"\n=== {title} ({len(rows)}) ===")
        for p in rows:
            kinds = ",".join(f"{k}:{n}" for k, n in sorted(paths[p].items()))
            print(f"  {p:<58} {kinds}")

    emit("READ — key name appears as a string literal in consumer source", read)
    emit("WEAK — name appears only as a bare identifier (likely coincidence)", weak)
    emit("DEAD — key name appears nowhere in consumer source", dead)
    print(f"\ntotal key paths: {len(paths)}  read: {len(read)}  weak: {len(weak)}  dead: {len(dead)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())