"""
A superseded artifact is present and not in force; a build writes only where its configuration says.

Supersession kept a predecessor out of what named it and left it in force wherever it acted by being
present: a superseded workflow kept a dispatch entry, and a catalog validation went on running one.
S8 now refuses a build in which anything superseded confers effect, whichever path let it through.

The output root was an argument, and two compositions from one surface could be written over each
other with both builds reporting success. Each build configuration now declares its root, and two
in-force configurations of one repository naming the same root are refused.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# The output root is resolved beside the governance surface's own structures; run from the regression,
# nothing else sets where that surface is.
os.environ.setdefault("PGC_PLATFORM_ROOT",
                      str(Path(__file__).resolve().parents[3] / "software_governance"))

from compiler.atoms.force import in_force
from compiler.governance_engine.platform_root import output_root
from compiler.graph.types import NodeKind
from compiler.stages.s8_verify import _verify_superseded_not_in_force

SUPERSEDED = {"superseded_by": ["probe::WF_UPDATE_V1"]}


def node(kind, address, frontmatter, code):
    return SimpleNamespace(kind=kind, address=address, frontmatter=frontmatter, namespace="probe",
                           artifact_code=code)


def graph(*nodes):
    return SimpleNamespace(nodes={f"probe::{n.artifact_code}": n for n in nodes})


def refused(content, coverage, g):
    return [e.fqdn_id for e in _verify_superseded_not_in_force(content, coverage, g)]


def test_an_artifact_is_in_force_unless_it_declares_a_successor():
    assert in_force({}) and in_force(None) and in_force({"superseded_by": []})
    assert not in_force(SUPERSEDED)


def test_a_superseded_workflow_with_an_entry_is_refused():
    g = graph(node(NodeKind.WF, 5, SUPERSEDED, "WF_UPDATE_V0"), node(NodeKind.WF, 6, {}, "WF_UPDATE_V1"))
    assert refused({"entry": {"5": {}, "6": {}}}, [], g) == ["probe::WF_UPDATE_V0"]
    assert refused({"entry": {"6": {}}}, [], g) == []


def test_a_superseded_intent_with_an_admission_contract_is_refused():
    g = graph(node(NodeKind.IN, 7, SUPERSEDED, "IN_UPDATE_V0"))
    assert refused({"admission": {"7": {}}}, [], g) == ["probe::IN_UPDATE_V0"]
    assert refused({"admission": {}}, [], g) == []


def test_a_superseded_invariant_whose_assertion_ran_is_refused():
    inv = node(None, -1, {**SUPERSEDED, "artifact_kind": "INVARIANT"}, "INVARIANT_OLD_RULE_V0")
    ran = [{"fqdn_id": "probe::ASSERT_OLD_RULE_V0"}]
    assert refused({}, ran, graph(inv)) == ["probe::INVARIANT_OLD_RULE_V0"]
    assert refused({}, [], graph(inv)) == []


def config(root_line):
    return ("# X\n\n## Machine\n\n```yaml\nartifact_kind: STRUCTURE\noutput_configuration:\n"
            f"{root_line}  artifacts:\n    layer: PROTOCOL_BUILD_ROOT\n    subpath: compiled/canonical\n```\n")


def resolve(configs: dict[str, str], code: str) -> Path:
    """Resolve `code`'s output root in a scratch repository holding `configs`."""
    repo = Path(tempfile.mkdtemp(prefix="pgc_root_"))
    try:
        (repo / "registry" / "structures").mkdir(parents=True)
        for name, text in configs.items():
            (repo / "registry" / "structures" / f"{name}.md").write_text(text)
        os.environ["PGC_DOMAIN_ROOTS"] = str(repo)
        import yaml
        from compiler.structure_loader import extract_yaml_from_machine_section
        structure = yaml.safe_load(extract_yaml_from_machine_section(configs[code]))
        structure["structure_artifact_code"] = code
        return output_root(structure).relative_to(repo)
    finally:
        os.environ.pop("PGC_DOMAIN_ROOTS", None)
        shutil.rmtree(repo)


def raises(fn, *args) -> str:
    try:
        fn(*args)
    except RuntimeError as exc:
        return str(exc)
    raise AssertionError("expected a refusal")


def test_a_build_writes_where_its_configuration_says():
    configs = {"STRUCTURE_BUILD_A_CONFIG_V0": config("  root: snapshot_a\n"),
               "STRUCTURE_BUILD_B_CONFIG_V0": config("  root: snapshot_b\n")}
    assert resolve(configs, "STRUCTURE_BUILD_A_CONFIG_V0") == Path("snapshot_a")


def test_two_configurations_naming_one_root_are_refused():
    configs = {"STRUCTURE_BUILD_A_CONFIG_V0": config("  root: snapshot\n"),
               "STRUCTURE_BUILD_B_CONFIG_V0": config("  root: snapshot\n")}
    assert "both declare output root" in raises(resolve, configs, "STRUCTURE_BUILD_A_CONFIG_V0")


def test_a_superseded_configuration_does_not_hold_its_root():
    retired = config("  root: snapshot\n").replace("artifact_kind: STRUCTURE\n",
                                                  "artifact_kind: STRUCTURE\nsuperseded_by:\n- x::Y\n")
    configs = {"STRUCTURE_BUILD_A_CONFIG_V1": config("  root: snapshot\n"),
               "STRUCTURE_BUILD_A_CONFIG_V0": retired}
    assert resolve(configs, "STRUCTURE_BUILD_A_CONFIG_V1") == Path("snapshot")


def test_a_configuration_naming_no_root_or_one_outside_its_repository_is_refused():
    assert "declares no output_configuration.root" in raises(
        resolve, {"STRUCTURE_BUILD_A_CONFIG_V0": config("")}, "STRUCTURE_BUILD_A_CONFIG_V0")
    assert "inside the repository" in raises(
        resolve, {"STRUCTURE_BUILD_A_CONFIG_V0": config("  root: ../elsewhere\n")},
        "STRUCTURE_BUILD_A_CONFIG_V0")


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
