"""Stage 5 mutation tests — the governance-closure hash tracks exactly the imported closure.

Four properties, each a real perturbation of the compiled surface:

  DETERMINISM   recompile the domain against unchanged governance  -> identical hash
  SENSITIVITY   change a domain-applicable platform invariant       -> hash changes
  ISOLATION     change a platform-ONLY invariant (not imported)     -> hash unchanged
  ENFORCEMENT   change platform governance, recompile platform only,
                re-assemble without recompiling the domain          -> assembly fails closed

Run:  python scripts/test_governance_provenance.py
"""

from __future__ import annotations

import json
import re
import yaml
import os
import subprocess
import sys
from pathlib import Path

COMPILER = Path(__file__).resolve().parents[1]
WORKSPACE = COMPILER.parent
COLLATZ = WORKSPACE / "conformance_workloads" / "workloads" / "collatz"
DOMAIN_ATT = COLLATZ / "snapshot" / "compiled" / "trust"

# Named, never defaulted: a platform is whatever a build config declares (6a §8) and a snapshot
# must name the profile it claims (1b §11). The tools have no defaults, so the caller names them.
PLATFORM_STRUCTURE = "STRUCTURE_BUILD_PLATFORM_CONFIG_V1"
SNAPSHOT_PROFILE = "GOVERNANCE_SURFACE_PROFILE_V0"

MACHINE = re.compile(r"(?P<h>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<t>\n```)", re.M | re.S)

# A domain-applicable invariant (imported into collatz) and a platform-only one (never imported).
IMPORTED = WORKSPACE / "software_governance" / "registry" / "execution_topology" / "invariants" / "INVARIANT_TOPOLOGY_ACYCLIC_V0.md"
PLATFORM_ONLY = WORKSPACE / "software_governance" / "registry" / "compiler" / "invariants" / "INVARIANT_COMPILER_NO_EXECUTION_V0.md"


def _run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def compile_platform() -> None:
    r = _run(["./compile.sh", PLATFORM_STRUCTURE], COMPILER)
    assert "0 failed" in r.stdout, f"platform compile failed:\n{r.stdout[-1500:]}"


def compile_domain() -> None:
    r = _run(["./compile_domain.sh", str(COLLATZ)], COMPILER)
    assert "0 failed" in r.stdout, f"domain compile failed:\n{r.stdout[-1500:]}"


def domain_hash() -> str:
    att = next(DOMAIN_ATT.glob("*/structure_attestation.json"))
    return json.loads(att.read_text())["imported_governance"]["governance_closure_hash"]


def perturb(path: Path, marker: str) -> bytes:
    """Add a harmless KEY inside the Machine block, changing its content_hash.

    It must be a key, not a comment. `content_hash` is taken over the machine block *parsed and
    canonically serialised* — prose declares nothing (MB-1), so an artifact's integrity value does
    not move when a comment is reworded. A comment therefore perturbs the file and not the artifact,
    and every property below would report a false negative: the closure hash cannot move, so
    SENSITIVITY sees no change and ENFORCEMENT has no drift for assembly to catch. An unconsumed key
    is refused by ASSERT_SCHEMA_CONFORMANCE_V0 (`additionalProperties: false`), and so is a repeated
    enum member. The schema is closed and every declared field carries meaning, so **no
    semantically-inert perturbation of an invariant exists** — which is itself the right design. The
    mutation therefore changes a real declared value: `core.violation_response` FAIL_IMMEDIATELY ->
    WARN, valid for a compiler-stage invariant and restored immediately afterwards. It is a genuine
    change to the governance that checked the build, which is precisely what the closure hash is
    supposed to track.
    """
    backup = path.read_bytes()
    text = path.read_text()
    m = MACHINE.search(text)
    y = yaml.safe_load(m.group("y"))
    assert y["core"]["violation_response"] == "FAIL_IMMEDIATELY", (
        f"{path.name}: expected FAIL_IMMEDIATELY to perturb, got {y['core']['violation_response']}")
    y["core"]["violation_response"] = "WARN"
    body = yaml.safe_dump(y, sort_keys=False, width=100).rstrip()
    path.write_text(text[: m.start()] + m.group("h") + body + m.group("t") + text[m.end():])
    return backup


def assemble() -> subprocess.CompletedProcess:
    # Named, not defaulted: a snapshot must name the profile it claims (1b §11).
    return _run(["./assemble.sh"], WORKSPACE / "snapshot_assembler",
                env={**os.environ, "PGC_SNAPSHOT_PROFILE": SNAPSHOT_PROFILE})


def main() -> int:
    print("baseline compile…")
    compile_platform()
    compile_domain()
    baseline = domain_hash()
    print(f"  baseline closure hash: {baseline[:16]}…")
    results: list[tuple[str, bool, str]] = []

    # DETERMINISM
    compile_domain()
    ok = domain_hash() == baseline
    results.append(("DETERMINISM  same governance -> identical hash", ok, domain_hash()[:16]))

    # ISOLATION — platform-only invariant is not in the closure
    bak = perturb(PLATFORM_ONLY, "iso")
    try:
        compile_platform()
        compile_domain()
        h = domain_hash()
        results.append(("ISOLATION    platform-only change -> hash unchanged", h == baseline, h[:16]))
    finally:
        PLATFORM_ONLY.write_bytes(bak)
        compile_platform()
        compile_domain()
    assert domain_hash() == baseline, "failed to restore baseline after ISOLATION"

    # SENSITIVITY — imported invariant changes the closure
    bak = perturb(IMPORTED, "sens")
    try:
        compile_platform()
        compile_domain()
        h = domain_hash()
        results.append(("SENSITIVITY  imported change -> hash changes", h != baseline, h[:16]))

        # ENFORCEMENT — platform now carries changed governance; the domain snapshot on disk still
        # records the OLD hash (we recompiled the domain above, so recompile-free-drift is simulated
        # by NOT recompiling the domain after this next platform-only change).
    finally:
        IMPORTED.write_bytes(bak)
        compile_platform()
        compile_domain()
    assert domain_hash() == baseline, "failed to restore baseline after SENSITIVITY"

    # ENFORCEMENT — mutate platform governance, recompile PLATFORM ONLY, re-assemble.
    bak = perturb(IMPORTED, "enforce")
    try:
        compile_platform()          # platform governance changed…
        # …domain deliberately NOT recompiled — its attestation still records the baseline hash.
        r = assemble()
        caught = "mismatch" in (r.stdout + r.stderr).lower() or r.returncode != 0
        results.append(("ENFORCEMENT  stale domain vs changed governance -> assembly fails", caught,
                        "blocked" if caught else "PASSED-THROUGH"))
    finally:
        IMPORTED.write_bytes(bak)
        compile_platform()
        compile_domain()
        assemble()

    print("\n--- results ---")
    ok_all = True
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<52} [{detail}]")
        ok_all &= ok
    print("\nprovenance restored:", "yes" if domain_hash() == baseline else "NO")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
