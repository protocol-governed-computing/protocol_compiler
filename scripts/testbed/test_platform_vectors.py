"""
The platform's own test vectors through a real platform build — the compiler's half of
software_governance/dossiers/platform_test_data.

The platform supplies transforms of its own, so its build compiles their vectors and proves them
(conformance::CONSTITUTION_TEST_DATA_V2 §4). Shown here, against a copy of the governance surface
compiled exactly as `compile.sh` compiles it: every platform vector is materialized as a declaration and
has its runnable cases written; each declaration defect in a platform vector stops the platform's build
on the rule that names it, so the rules written for vectors judge the platform's as they judge a
domain's; and a build records the capabilities it carried in from the surface it imports, which is how
conformance tells what a build supplies from what it only carries.

Writes only to a temporary directory.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[3]
SURFACE = W / "software_governance"
PLATFORM = "STRUCTURE_BUILD_PLATFORM_CONFIG_V2"
VECTOR = "capability_transforms/registry/test_data/TEST_DATA_CT_PURE_LOOKUP_V0.md"
DOMAIN = W / "business_domains" / "ai_governance"
PLATFORM_TRANSFORMS = 13

# tamper -> (text substitution in the lookup vector, the assertion that must refuse it)
TAMPERS = {
    "an output the transform does not declare": (
        ("  expected:\n    result: active\n", "  expected:\n    result: active\n    bogus: 1\n"),
        "ASSERT_TEST_DATA_MATCH_CT_OUTPUT_V0"),
    "an assertion mode nothing declares": (
        ("  expected:\n    result: active\n", "  assertions:\n    result: {mode: fuzzy}\n"),
        "ASSERT_CONFORMANCE_ASSERTION_MODE_VALID_V1"),
    "a recorded result for an atom": (
        ("  expected:\n    result: active\n", "  expected:\n    result: active\n  recorded:\n    x: {y: 1}\n"),
        "ASSERT_TEST_DATA_RECORDS_MATCH_PURITY_V0"),
    "a case with no outcome": (
        ("- case_id: lookup_string_value\n  expected_outcome: SUCCESS\n", "- case_id: lookup_string_value\n"),
        "ASSERT_SCHEMA_CONFORMANCE_V0"),
    "a field outside the schema": (
        ("target:", "test_cases: []\ntarget:"), "ASSERT_SCHEMA_CONFORMANCE_V0"),
}


def _compile(structure: str, platform: Path, snapshot: Path, domain: Path | None = None) -> tuple[int, str]:
    env = {**os.environ, "PGC_PLATFORM_ROOT": str(platform), "PGC_SNAPSHOT_ROOT": str(snapshot),
           "PYTHONPATH": str(W / "protocol_compiler")}
    if domain:
        env["PGC_DOMAIN_ROOTS"] = str(domain)
    run = subprocess.run([sys.executable, "-m", "compiler.cli", "compile", "--structure", structure],
                         capture_output=True, text=True, env=env, cwd=W / "protocol_compiler")
    return run.returncode, run.stdout + run.stderr


def _surface(root: Path, vector_text: str | None = None) -> Path:
    surface = root / "software_governance"
    shutil.copytree(SURFACE, surface, ignore=shutil.ignore_patterns(
        "snapshot", "snapshot_fed", "snapshot_mw", "__pycache__", ".git", "dossiers"))
    if vector_text is not None:
        (surface / VECTOR).write_text(vector_text)
    return surface


def test_the_platform_materializes_its_vectors_and_writes_their_cases():
    with tempfile.TemporaryDirectory() as tmp:
        surface = _surface(Path(tmp))
        code, out = _compile(PLATFORM, surface, surface / "snapshot")
        assert code == 0, out[-2000:]
        compiled = surface / "snapshot" / "compiled"
        vectors = sorted(json.loads(p.read_text())["frontmatter"]["target"]
                         for p in (compiled / "canonical" / "test_data").glob("*.json"))
        declared = sorted((surface / "capability_transforms/registry/test_data").glob("*.md"))
        assert len(vectors) == len(declared) == PLATFORM_TRANSFORMS - 1, vectors
        cases = [json.loads(p.read_text()) for p in (compiled / "transform_conformance").glob("*.json")]
        assert cases and {c["ct_fqdn"] for c in cases} == set(vectors), sorted({c["ct_fqdn"] for c in cases})


def test_each_defect_in_a_platform_vector_stops_the_platform_build_on_its_own_rule():
    clean = (SURFACE / VECTOR).read_text()
    for name, ((old, new), rule) in TAMPERS.items():
        assert clean.count(old) == 1, name
        with tempfile.TemporaryDirectory() as tmp:
            surface = _surface(Path(tmp), clean.replace(old, new))
            code, out = _compile(PLATFORM, surface, surface / "snapshot")
            assert code != 0 and rule in out, (name, rule, out[-1500:])


def test_a_build_records_what_it_carried_in_and_the_platform_carries_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        surface = _surface(Path(tmp))
        code, out = _compile(PLATFORM, surface, surface / "snapshot")
        assert code == 0, out[-2000:]
        platform = json.loads((surface / "snapshot/compiled/trust/platform/structure_attestation.json").read_text())
        assert "imported_capabilities" not in platform, platform.get("imported_capabilities")

        domain = Path(tmp) / "ai_governance"
        shutil.copytree(DOMAIN, domain, ignore=shutil.ignore_patterns("snapshot", "__pycache__"))
        manifest = next((domain / "registry/structures").glob("STRUCTURE_BUILD_*_CONFIG_V*.md")).stem
        code, out = _compile(manifest, surface, domain / "snapshot", domain)
        assert code == 0, out[-2000:]
        attestation = json.loads(
            (domain / "snapshot/compiled/trust/ai_governance/structure_attestation.json").read_text())
        carried = attestation.get("imported_capabilities", [])
        transforms = sorted(json.loads(p.read_text())["fqdn_id"] for p in
                            (domain / "snapshot/compiled/canonical/capability_transforms").glob("*.json"))
        assert carried == sorted(carried), carried
        assert [t for t in transforms if t in carried] == \
            [t for t in transforms if not t.startswith("ai_governance::")], (carried, transforms)
        assert not any(t.startswith("ai_governance::") for t in carried), carried


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # report every test, then fail the run
            failed += 1
            print(f"  FAIL  {name}: {exc!r}"[:1500])
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
