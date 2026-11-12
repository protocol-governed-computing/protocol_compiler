"""
The sealed Governance Ontology and the compiler's built-in classification state one ontology.

`ASSERT_GOVERNANCE_ONTOLOGY_AGREES_V0` compares `artifact::VOCAB_GOVERNANCE_ONTOLOGY_V0` with
`artifact_kinds._DESCRIPTORS`, group by group: the categories and provenances, the kinds in each
category and provenance, and the categories in each runtime disposition. A kind listed twice on one
axis is refused. A build that does not author the vocabulary has nothing to compare.

Run:  python scripts/testbed/test_governance_ontology.py
"""
import sys

from compiler.governance_engine.assertions.handlers.assert_governance_ontology_agrees_v0 import (
    ONTOLOGY_FQDN, _built_in, execute as agrees,
)


def vocabulary(**changes):
    """The ontology as the built-in table states it, written as vocabulary groups, then changed."""
    frontmatter = {"fqdn": ONTOLOGY_FQDN, "artifact_kind": "VOCABULARY"}
    for name, entries in _built_in().items():
        casing = "UPPER_SNAKE" if name.startswith(("category_", "provenance_")) else "lower_snake"
        frontmatter[name] = {"casing": casing, "entries": sorted(entries)}
    for name, entries in changes.items():
        if entries is None:
            frontmatter.pop(name, None)
        else:
            frontmatter[name] = {"casing": "UPPER_SNAKE", "entries": entries}
    return {"fqdn_id": ONTOLOGY_FQDN, "artifact_code": "VOCAB_GOVERNANCE_ONTOLOGY_V0",
            "frontmatter": frontmatter}


def found(*artifacts):
    return [v["violation"] for v in agrees(list(artifacts), {})["violations"]]


def test_the_same_ontology_passes():
    assert found(vocabulary()) == [], found(vocabulary())


def test_a_kind_in_another_category_is_refused():
    drifted = vocabulary(category_participatory=["ACTOR", "WORKFLOW"],
                         category_operational=["CAPABILITY_SIDE_EFFECT", "CAPABILITY_TRANSFORM",
                                               "INTENT", "RUNTIME_BINDING"])
    assert any("category_participatory" in v for v in found(drifted)), found(drifted)
    assert any("category_operational" in v for v in found(drifted)), found(drifted)


def test_a_kind_classified_twice_is_refused():
    twice = vocabulary(category_participatory=["ACTOR", "EVENT"])
    assert "'EVENT' is classified more than once: ['category_evidential', 'category_participatory']" \
        in found(twice), found(twice)


def test_a_missing_group_is_refused():
    missing = vocabulary(provenance_derived=None)
    assert any("provenance_derived" in v for v in found(missing)), found(missing)


def test_a_group_the_table_does_not_have_is_refused():
    extra = vocabulary(provenance_produced=["EVENT"])
    assert any("provenance_produced" in v for v in found(extra)), found(extra)


def test_a_build_without_the_vocabulary_examines_nothing():
    result = agrees([{"fqdn_id": "d::VOCAB_OTHER_V0", "frontmatter": {}}], {})
    assert result == {"assert_count": 0, "violations": [], "status": "PASSED"}, result


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
