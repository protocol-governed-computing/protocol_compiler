"""Machine-block mutation verifier — proves whether a key is load-bearing.

The static census (``machine_key_census.py``) only shows whether a key *name*
appears in consumer source. This proves consumption behaviourally:

  1. compile → record a semantic fingerprint of the snapshot
  2. delete one key path from one artifact's ``## Machine`` block
  3. recompile → fingerprint again, then restore the artifact
  4. same fingerprint and same compile outcome ⇒ the key is DEAD

The fingerprint deliberately EXCLUDES the fields that echo the source verbatim
(``content``, ``content_hash``, ``frontmatter`` in canonical projections) and
any attestation digest derived from them — otherwise every edit registers as a
change and nothing can ever be shown dead.

Usage:
    python scripts/machine_key_mutation.py \
        --artifact ../software_governance/registry/FB_TOPOLOGY/invariants/INVARIANT_TOPOLOGY_ACYCLIC_V0.md \
        --key core.anti_patterns --key core.violation_response
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

MACHINE_BLOCK = re.compile(
    r"(?P<head>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<tail>\n```)",
    re.MULTILINE | re.DOTALL,
)

COMPILER_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = COMPILER_ROOT.parent

# Fields that echo the authored source verbatim, or are rollup digests over that
# echo. They change on ANY edit — including a comment — so they carry no signal
# about whether the compiler consumed the key.
ECHO_FIELDS = {"content", "content_hash", "frontmatter"}
VOLATILE_KEYS = {
    "timestamp", "generated_at", "compiled_at", "build_id", "duration_ms",
    "signed_at", "signature", "attestation_hash",
    "projection_hash", "tokenized_projection_hash",
}
# The compiler's own semantic identity of the build: derived from the typed graph
# (nodes, addresses, edges), not from source bytes. If these are unchanged, the
# deleted key contributed nothing to compiled meaning.
SEMANTIC_HASH_KEYS = ("graph_topology_hash", "graph_address_hash")


def _strip(obj: Any, drop: set[str]) -> Any:
    if isinstance(obj, dict):
        return {k: _strip(v, drop) for k, v in sorted(obj.items()) if k not in drop}
    if isinstance(obj, list):
        return [_strip(v, drop) for v in obj]
    return obj


def fingerprint(snapshot_root: Path) -> str:
    """Semantic digest of the snapshot, ignoring echoed source and rollup digests.

    Includes the compiler's own ``graph_topology_hash`` / ``graph_address_hash``
    (kept, not stripped) plus every non-echo projection body.
    """
    h = hashlib.sha256()
    for path in sorted(snapshot_root.rglob("*.json")):
        rel = path.relative_to(snapshot_root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        drop = VOLATILE_KEYS | (ECHO_FIELDS if rel.startswith("compiled/canonical/") else set())
        h.update(rel.encode())
        h.update(json.dumps(_strip(data, drop), sort_keys=True, default=str).encode())
    return h.hexdigest()


def delete_key(data: dict, dotted: str) -> bool:
    """Remove ``a.b.c`` from a nested dict. Returns False if absent."""
    parts = dotted.split(".")
    cur: Any = data
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    if not isinstance(cur, dict) or parts[-1] not in cur:
        return False
    del cur[parts[-1]]
    return True


def rewrite_machine(path: Path, dotted: str) -> bool:
    """Rewrite the artifact with ``dotted`` deleted from its Machine block."""
    text = path.read_text(encoding="utf-8")
    m = MACHINE_BLOCK.search(text)
    if not m:
        return False
    data = yaml.safe_load(m.group("y").rstrip())
    if not isinstance(data, dict) or not delete_key(data, dotted):
        return False
    new_yaml = yaml.safe_dump(data, sort_keys=False, default_flow_style=False).rstrip()
    path.write_text(
        text[: m.start()] + m.group("head") + new_yaml + m.group("tail") + text[m.end():],
        encoding="utf-8",
    )
    return True


def compile_once(structure: str) -> tuple[bool, str]:
    proc = subprocess.run(
        ["./compile.sh", structure],
        cwd=COMPILER_ROOT, capture_output=True, text=True,
    )
    ok = proc.returncode == 0 and "0 failed" in proc.stdout
    return ok, (proc.stdout + proc.stderr)[-2000:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True, type=Path)
    ap.add_argument("--key", action="append", required=True,
                    help="dotted Machine-block key path to delete; repeatable")
    ap.add_argument("--structure", default="STRUCTURE_BUILD_PLATFORM_CONFIG_V1")
    ap.add_argument("--snapshot", type=Path,
                    default=WORKSPACE / "software_governance" / "snapshot")
    args = ap.parse_args()

    artifact = args.artifact.resolve()
    if not artifact.is_file():
        print(f"no such artifact: {artifact}", file=sys.stderr)
        return 2

    ok, log = compile_once(args.structure)
    if not ok:
        print("baseline compile FAILED — fix the tree before mutating\n" + log, file=sys.stderr)
        return 2
    baseline = fingerprint(args.snapshot)
    print(f"baseline fingerprint: {baseline[:16]}\n")

    backup = artifact.read_bytes()
    results: list[tuple[str, str]] = []
    try:
        for key in args.key:
            artifact.write_bytes(backup)
            if not rewrite_machine(artifact, key):
                results.append((key, "ABSENT — key not present in this artifact"))
                continue
            ok, log = compile_once(args.structure)
            if not ok:
                verdict = "LIVE — compile fails without it"
            else:
                verdict = ("DEAD — compiles clean, snapshot unchanged"
                           if fingerprint(args.snapshot) == baseline
                           else "LIVE — snapshot changes")
            results.append((key, verdict))
            print(f"  {key:<48} {verdict}")
    finally:
        artifact.write_bytes(backup)
        compile_once(args.structure)  # restore snapshot to baseline

    print("\n--- summary ---")
    for key, verdict in results:
        print(f"  {key:<48} {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())