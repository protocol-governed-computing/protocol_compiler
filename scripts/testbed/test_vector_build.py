"""
Test vectors through a real domain build — the compiler's half of transform_conformance, end to end.

The assertion tests judge each check in isolation, and all of them passed while the build could not
parse a vector at all and silently skipped two of the rules written for vectors. So this builds a real
domain: a copy of the reference workload, given one vector, compiled against the platform surface
exactly as `compile_domain.sh` builds any domain: compile, then conformance. The clean vector must compile,
write its runnable cases and prove its transform; each declaration defect must stop the compile on the
rule that names it, before conformance runs; a transform that does not do what its vector says must
fail the build at conformance.

Needs the platform surface compiled (the regression compiles it first). Writes only to a temporary
directory.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[3]
COLLATZ = W / "conformance_workloads" / "workloads" / "collatz"
MANIFEST = "registry/structures/STRUCTURE_BUILD_WORKLOAD_CONFIG_V0.md"
VECTOR = "registry/test_data/TEST_DATA_CT_PURE_COLLATZ_STEP_V0.md"

CLEAN = '''# TEST_DATA_CT_PURE_COLLATZ_STEP_V0

## Machine

```yaml
fqdn: workload::TEST_DATA_CT_PURE_COLLATZ_STEP_V0
artifact_kind: TEST_DATA
version: V0
governed_by: conformance::CONSTITUTION_TEST_DATA_V1
authority: pgc.platform
concern: workload
core:
  summary: Collatz sequences for small numbers
target: workload::CT_PURE_COLLATZ_STEP_V0
cases:
- case_id: three_and_six
  expected_outcome: SUCCESS
  bindings:
    numbers: [3, 6]
  expected:
    sequences:
      "3": [3, 10, 5, 16, 8, 4, 2, 1]
      "6": [6, 3, 10, 5, 16, 8, 4, 2, 1]
- case_id: zero_refused
  expected_outcome: VIOLATION
  bindings:
    numbers: [0]
```

## Intent

Collatz sequences for small numbers, and the refusal of a number below one.
'''

# tamper -> (text substitution, the assertion that must refuse it)
TAMPERS = {
    "an output the transform does not declare": (
        ("  expected:\n", "  expected:\n    bogus: 1\n"), "ASSERT_TEST_DATA_MATCH_CT_OUTPUT_V0"),
    "an assertion mode nothing declares": (
        ("  expected_outcome: VIOLATION\n",
         "  expected_outcome: SUCCESS\n  assertions:\n    sequences: {mode: fuzzy}\n"),
        "ASSERT_CONFORMANCE_ASSERTION_MODE_VALID_V1"),
    "a recorded result for an atom": (
        ("  expected_outcome: VIOLATION\n",
         "  expected_outcome: VIOLATION\n  recorded:\n    offered: {x: 1}\n"),
        "ASSERT_TEST_DATA_RECORDS_MATCH_PURITY_V0"),
    "a target the build does not declare": (
        ("target: workload::CT_PURE_COLLATZ_STEP_V0", "target: workload::CT_PURE_NONE_V0"),
        "ASSERT_TEST_DATA_MATCH_CT_OUTPUT_V0"),
    "a field outside the schema": (
        ("target:", "test_cases: []\ntarget:"), "ASSERT_SCHEMA_CONFORMANCE_V0"),
}


def _domain(root: Path, vector: str) -> Path:
    domain = root / "collatz"
    shutil.copytree(COLLATZ, domain, ignore=shutil.ignore_patterns("snapshot", "__pycache__"))
    manifest = domain / MANIFEST
    text = manifest.read_text()
    text = text.replace("  - TI\n  - TE\noutput_configuration:\n",
                        "  - TI\n  - TE\n  - TEST_DATA\noutput_configuration:\n"
                        "  conformance:\n    layer: GOVERNANCE\n    subpath: compiled/transform_conformance\n")
    assert "TEST_DATA" in text, "the reference workload's manifest changed shape; update this test"
    manifest.write_text(text)
    (domain / VECTOR).parent.mkdir(parents=True, exist_ok=True)
    (domain / VECTOR).write_text(vector)
    return domain


def _build(vector: str) -> tuple[int, str, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        domain = _domain(Path(tmp), vector)
        run = subprocess.run([str(W / "protocol_compiler" / "compile_domain.sh"), str(domain)],
                             capture_output=True, text=True)
        cases = sorted(p.name for p in (domain / "snapshot/compiled/transform_conformance").glob("*.json")
                       if p.name != "result.json")
        if cases:
            first = json.loads((domain / "snapshot/compiled/transform_conformance" / cases[0]).read_text())
            assert first["ct_fqdn"] == "workload::CT_PURE_COLLATZ_STEP_V0", first
        return run.returncode, run.stdout + run.stderr, cases


def test_a_clean_vector_compiles_and_writes_its_cases():
    code, out, cases = _build(CLEAN)
    assert code == 0, out[-2000:]
    assert cases == ["workload__CT_PURE_COLLATZ_STEP_V0__three_and_six.json",
                     "workload__CT_PURE_COLLATZ_STEP_V0__zero_refused.json"], cases


def test_each_defect_stops_the_build_on_its_own_rule():
    for name, ((old, new), rule) in TAMPERS.items():
        assert CLEAN.count(old) == 1, name
        code, out, _ = _build(CLEAN.replace(old, new))
        assert code != 0 and rule in out, (name, rule, out[-1500:])
        # Conformance runs only after a successful compile: a domain the compiler refused is never run.
        assert "[conformance]" not in out, (name, out[-800:])


def test_the_build_proves_the_vector_after_compiling():
    code, out, _ = _build(CLEAN)
    assert code == 0, out[-1500:]
    assert "[conformance] workload: 1 proven, 1 unproven, 0 refused" in out, out[-800:]
    assert "UNPROVEN  workload::CT_PURE_TERMINATION_CHECK_V0" in out, out[-800:]


def test_a_transform_that_does_not_do_what_its_vector_says_fails_the_build():
    code, out, _ = _build(CLEAN.replace('"3": [3, 10,', '"3": [3, 11,'))
    assert code != 0, out[-1500:]
    assert "Build Summary: 1 succeeded" in out and "1 refused" in out, out[-1500:]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # report every test, then fail the run
            failed += 1
            print(f"  FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
