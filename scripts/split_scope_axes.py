"""Correction — separate the two scope axes conflated in stage 1.

`assert_projection.scope.applies_to` had a pre-existing meaning: the LAYER/SURFACE an
assertion governs (PLATFORM, or a domain layer), read by the surface-closure handlers.
Stage 1 wrongly repurposed it as artifact-KIND applicability, silently making the
platform CT/CS surface-closure checks vacuous.

This restores the field to its layer meaning and moves kind applicability to a distinct
field, `assert_projection.applies_to_kinds`. One field, one axis.

  scope.applies_to    -> layer/surface tokens (PLATFORM, <domain layer>); only where a
                         surface-scoped handler needs it. Restored, not invented.
  applies_to_kinds     -> the artifact kinds an invariant governs (the stage-1 tokens),
                         authoritative for the governance-import filter.

Usage:
    python scripts/split_scope_axes.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / "platform" / "registry"

MACHINE = re.compile(
    r"(?P<head>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<tail>\n```)",
    re.MULTILINE | re.DOTALL,
)

# Invariants whose scope.applies_to was genuinely a LAYER/SURFACE scope before stage 1,
# read by a surface-scoped handler. Restored here to [PLATFORM]. Every other invariant's
# stage-1 value was a kind token and moves wholesale to applies_to_kinds.
LAYER_SCOPED = {
    "INVARIANT_CT_SURFACE_CLOSED_V1": ["PLATFORM"],
    "INVARIANT_CS_SURFACE_CLOSED_V1": ["PLATFORM"],
    "INVARIANT_RUNTIME_INVARIANT_WIRED_V0": ["PLATFORM"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    n = 0
    for path in sorted(REGISTRY.rglob("INVARIANT_*.md")):
        text = path.read_text(encoding="utf-8")
        m = MACHINE.search(text)
        if not m:
            continue
        data = yaml.safe_load(m.group("y").rstrip())
        proj = data.get("assert_projection")
        if not isinstance(proj, dict):
            continue
        scope = proj.get("scope") or {}
        kinds = scope.get("applies_to")
        if kinds is None:
            continue

        # Move the stage-1 kind tokens to applies_to_kinds.
        proj["applies_to_kinds"] = list(kinds)
        # Restore layer scope only where it genuinely existed; drop the field otherwise.
        if path.stem in LAYER_SCOPED:
            proj["scope"] = {"applies_to": LAYER_SCOPED[path.stem]}
        else:
            proj.pop("scope", None)

        n += 1
        if not args.dry_run:
            body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                                  allow_unicode=True, width=100).rstrip()
            path.write_text(
                text[: m.start()] + m.group("head") + body + m.group("tail") + text[m.end():],
                encoding="utf-8",
            )

    verb = "would split" if args.dry_run else "split"
    print(f"  {verb} scope axes on {n} invariants")
    print(f"  layer/surface scope restored on: {sorted(LAYER_SCOPED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())