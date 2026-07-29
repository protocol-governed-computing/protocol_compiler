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
import subprocess
import sys
from pathlib import Path

COMPILER = Path(__file__).resolve().parents[1]
WORKSPACE = COMPILER.parent
COLLATZ = WORKSPACE / "conformance_workloads" / "workloads" / "collatz"
DOMAIN_ATT = COLLATZ / "snapshot" / "compiled" / "trust"

MACHINE = re.compile(r"(?P<h>^## Machine\s*\n+```yaml\s*\n)(?P<y>.*?)(?P<t>\n```)", re.M | re.S)

# A domain-applicable invariant (imported into collatz) and a platform-only one (never imported).
IMPORTED = WORKSPACE / "software_governance" / "registry" / "execution_topology" / "invariants" / "INVARIANT_TOPOLOGY_ACYCLIC_V0.md"
PLATFORM_ONLY = WORKSPACE / "software_governance" / "registry" / "compiler" / "invariants" / "INVARIANT_COMPILER_NO_EXECUTION_V0.md"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def compile_platform() -> None:
    r = _run(["./compile.sh"], COMPILER)
    assert "0 failed" in r.stdout, f"platform compile failed:\n{r.stdout[-1500:]}"


def compile_domain() -> None:
    r = _run(["./compile_domain.sh", str(COLLATZ)], COMPILER)
    assert "0 failed" in r.stdout, f"domain compile failed:\n{r.stdout[-1500:]}"


def domain_hash() -> str:
    att = next(DOMAIN_ATT.glob("*/structure_attestation.json"))
    return json.loads(att.read_text())["imported_governance"]["governance_closure_hash"]


def perturb(path: Path, marker: str) -> bytes:
    """Append a harmless comment line inside the Machine block, changing its content_hash."""
    backup = path.read_bytes()
    text = path.read_text()
    m = MACHINE.search(text)
    body = m.group("y").rstrip() + f"\n# provenance-mutation-{marker}"
    path.write_text(text[: m.start()] + m.group("h") + body + m.group("t") + text[m.end():])
    return backup


def assemble() -> subprocess.CompletedProcess:
    return _run(["./assemble.sh"], WORKSPACE / "snapshot_assembler")


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
