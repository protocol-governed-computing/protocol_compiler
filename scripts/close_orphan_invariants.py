"""Close orphan invariants — declare each in its governing constitution.

An invariant no constitution names enforces a rule that was never constitutionally
established. Every orphan already declares `governed_by`, so the constitution that
should declare it is known; this adds the missing rule there.

`applies_to` is derived from what the invariant is about: an artifact-type token when
the invariant code names one, otherwise the constitution's own `core.governs`, otherwise
ALL_ARTIFACTS. The field has no consumer yet — it is constrained to shape only — so the
derivation is deliberately conservative rather than inventive.

Usage:
    python scripts/close_orphan_invariants.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / "software_governance" / "registry"

MACHINE = re.compile(
    r"(?P<head>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<tail>\n```)",
    re.MULTILINE | re.DOTALL,
)

# Artifact-type token when the invariant code names one. Ordered: longest first so
# TRANSPORT_ wins over T-prefixed shorter tokens.
TYPE_TOKENS = [
    ("TRANSPORT_", "TI_TE"),
    ("TOPOLOGY_", "ALL_ARTIFACTS"),
    ("CONFORMANCE_", "TEST_DATA"),
    ("COMPILER_", "SYSTEM"),
    ("IDENTITY_", "ALL_ARTIFACTS"),
    ("BINDING_", "RB"),
    ("CT_", "CT"),
    ("CS_", "CS"),
    ("CC_", "CC"),
    ("WF_", "WF"),
    ("RB_", "RB"),
    ("AC_", "AC"),
]


def namespace_of(path: Path) -> str:
    fb = next(p for p in path.parts if p.startswith("FB_"))
    return "fb." + fb[len("FB_"):].lower()


def derive_applies_to(invariant_code: str, con_governs: list | None) -> str:
    subject = invariant_code[len("INVARIANT_"):]
    for prefix, token in TYPE_TOKENS:
        if subject.startswith(prefix):
            return token
    if con_governs:
        return str(con_governs[0])
    return "ALL_ARTIFACTS"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    blocks: dict[Path, dict] = {}
    for md in sorted(REGISTRY.rglob("*.md")):
        m = MACHINE.search(md.read_text(encoding="utf-8"))
        if not m:
            continue
        d = yaml.safe_load(m.group("y").rstrip())
        if isinstance(d, dict):
            blocks[md] = d

    invariants = {
        f"{namespace_of(p)}::{p.stem}": (p, d)
        for p, d in blocks.items() if d.get("artifact_kind") == "INVARIANT"
    }
    constitutions = {
        f"{namespace_of(p)}::{p.stem}": (p, d)
        for p, d in blocks.items() if d.get("artifact_kind") == "CONSTITUTION"
    }

    named = {
        r.get("enforced_by")
        for _p, d in constitutions.values()
        for r in (d.get("rules") or [])
        if isinstance(r.get("enforced_by"), str) and "::" in r["enforced_by"]
    }

    additions: dict[str, list[dict]] = {}
    unresolved: list[str] = []
    for fqdn in sorted(invariants):
        if fqdn in named:
            continue
        _p, inv = invariants[fqdn]
        gov = inv.get("governed_by")
        gov = gov[0] if isinstance(gov, list) else gov
        if gov not in constitutions:
            unresolved.append(f"{fqdn} -> {gov}")
            continue
        con_governs = (constitutions[gov][1].get("core") or {}).get("governs")
        rule = {
            "applies_to": derive_applies_to(fqdn.split("::")[1], con_governs),
            "enforced_by": fqdn,
        }
        additions.setdefault(gov, []).append(rule)
        print(f"  {gov.split('::')[1]:<38} += {rule['applies_to']:<14} {fqdn.split('::')[1]}")

    for gov, rules in additions.items():
        path, data = constitutions[gov]
        data.setdefault("rules", []).extend(rules)
        if args.dry_run:
            continue
        text = path.read_text(encoding="utf-8")
        m = MACHINE.search(text)
        body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                              allow_unicode=True, width=100).rstrip()
        path.write_text(
            text[: m.start()] + m.group("head") + body + m.group("tail") + text[m.end():],
            encoding="utf-8",
        )

    verb = "would add" if args.dry_run else "added"
    print(f"\n  {verb} {sum(len(v) for v in additions.values())} rules "
          f"across {len(additions)} constitutions")
    if unresolved:
        print(f"  UNRESOLVED governed_by ({len(unresolved)}):")
        for u in unresolved:
            print(f"     {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())