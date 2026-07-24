"""B1 — populate the authoritative `fqdn:` on every registry artifact.

The value written is the artifact's CURRENT compiled FQDN (read from the compiler's own
canonical output), so identity is preserved exactly — this is a mechanism migration, not a
rename. `fqdn` is inserted as the first key of the `## Machine` block.

Idempotent. Run after a successful compile of both platform and the collatz domain (so the
canonical maps exist).

Usage: python scripts/populate_declared_fqdn.py [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
MACHINE = re.compile(
    r"(?P<head>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<tail>\n```)", re.M | re.S
)

CANONICAL_ROOTS = [
    WORKSPACE / "platform" / "snapshot" / "compiled" / "canonical",
    WORKSPACE / "platform" / "reference_workloads" / "collatz" / "snapshot" / "compiled" / "canonical",
]
REGISTRY_GLOBS = [
    str(WORKSPACE / "platform" / "registry" / "**" / "*.md"),
    str(WORKSPACE / "platform" / "reference_workloads" / "collatz" / "registry" / "**" / "*.md"),
]


def code_to_fqdn() -> dict[str, str]:
    m: dict[str, str] = {}
    for root in CANONICAL_ROOTS:
        for f in root.rglob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            code, fq = d.get("artifact_code"), d.get("fqdn_id")
            if code and fq:
                if code in m and m[code] != fq:
                    raise SystemExit(f"ambiguous artifact_code {code}: {m[code]} vs {fq}")
                m[code] = fq
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    m = code_to_fqdn()
    changed = skipped = 0
    for pattern in REGISTRY_GLOBS:
        for path_str in sorted(glob.glob(pattern, recursive=True)):
            path = Path(path_str)
            code = path.stem
            fqdn = m.get(code)
            if fqdn is None:
                raise SystemExit(f"no compiled FQDN for {code} — recompile first")
            text = path.read_text(encoding="utf-8")
            mm = MACHINE.search(text)
            if not mm:
                continue
            data = yaml.safe_load(mm.group("y").rstrip())
            if not isinstance(data, dict):
                continue
            if data.get("fqdn") == fqdn and list(data)[0] == "fqdn":
                skipped += 1
                continue
            # fqdn first, then existing keys (minus any stale fqdn)
            rest = {k: v for k, v in data.items() if k != "fqdn"}
            ordered = {"fqdn": fqdn, **rest}
            body = yaml.safe_dump(ordered, sort_keys=False, default_flow_style=False,
                                  allow_unicode=True, width=100).rstrip()
            changed += 1
            if not args.dry_run:
                path.write_text(
                    text[: mm.start()] + mm.group("head") + body + mm.group("tail") + text[mm.end():],
                    encoding="utf-8",
                )

    verb = "would populate" if args.dry_run else "populated"
    print(f"  {verb} fqdn on {changed} artifacts ({skipped} already current)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
