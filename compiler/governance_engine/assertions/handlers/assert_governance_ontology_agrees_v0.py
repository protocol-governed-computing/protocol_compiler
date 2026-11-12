"""ASSERT_GOVERNANCE_ONTOLOGY_AGREES_V0 Handler

The sealed Governance Ontology (`artifact::VOCAB_GOVERNANCE_ONTOLOGY_V0`) and the compiler's
built-in classification (`artifact_kinds._DESCRIPTORS`) MUST state one ontology. The compiler needs
the built-in table to compile the vocabulary at all, so the table stays; this check keeps the two from
drifting. Pure rule checker — reads the artifact set from context.

A build that does not author the vocabulary has nothing to compare: imported governance is never a
subject, so a domain build passes with nothing examined.
"""

from compiler.governance_engine import artifact_kinds

ONTOLOGY_FQDN = "artifact::VOCAB_GOVERNANCE_ONTOLOGY_V0"
_ASSERT = "ASSERT_GOVERNANCE_ONTOLOGY_AGREES_V0"


def _symbol(text: str) -> str:
    """A built-in name as the vocabulary spells it: `not independently executable` →
    `not_independently_executable`, `Definitional` → `definitional`."""
    return text.lower().replace(" ", "_")


def _built_in() -> dict[str, set[str]]:
    """The built-in classification, as the groups the vocabulary declares."""
    groups: dict[str, set[str]] = {
        "semantic_categories": {_symbol(c) for c in artifact_kinds.SEMANTIC_CATEGORIES},
        "provenances": {_symbol(p) for p in artifact_kinds.PROVENANCES},
    }
    for descriptor in artifact_kinds._DESCRIPTORS:
        if not (descriptor.artifact_kind and descriptor.semantic_category):
            continue                       # a kind not yet authorized is classified nowhere
        groups.setdefault(f"category_{_symbol(descriptor.semantic_category)}", set()).add(
            descriptor.artifact_kind)
        groups.setdefault(f"provenance_{_symbol(descriptor.provenance)}", set()).add(
            descriptor.artifact_kind)
    for category in artifact_kinds.SEMANTIC_CATEGORIES:
        disposition = artifact_kinds._RUNTIME_DISPOSITION[category]
        groups.setdefault(f"runtime_disposition_{_symbol(disposition)}", set()).add(_symbol(category))
    return groups


def _sealed(frontmatter: dict) -> dict[str, set[str]]:
    """The vocabulary's groups, by name."""
    return {
        name: {str(entry) for entry in (group.get("entries") or [])}
        for name, group in frontmatter.items()
        if isinstance(group, dict) and "entries" in group
    }


def _once(groups: dict[str, set[str]], prefix: str) -> dict[str, list[str]]:
    """Each symbol listed under more than one group with this prefix."""
    seen: dict[str, list[str]] = {}
    for name, entries in groups.items():
        if name.startswith(prefix):
            for entry in entries:
                seen.setdefault(entry, []).append(name)
    return {entry: names for entry, names in seen.items() if len(names) > 1}


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    ontology = [a for a in artifacts if a.get("fqdn_id") == ONTOLOGY_FQDN]
    violations = []
    for artifact in ontology:
        code = artifact.get("artifact_code", "UNKNOWN")
        sealed, built_in = _sealed(artifact.get("frontmatter") or {}), _built_in()
        for name in sorted(set(sealed) | set(built_in)):
            if sealed.get(name, set()) != built_in.get(name, set()):
                violations.append({
                    "assert": _ASSERT,
                    "artifact": code,
                    "violation": (f"group {name!r}: the vocabulary lists {sorted(sealed.get(name, set()))}, "
                                  f"the compiler's built-in table {sorted(built_in.get(name, set()))}"),
                    "fix": "State one ontology: change the vocabulary or the built-in table so the two agree",
                })
        for prefix in ("category_", "provenance_", "runtime_disposition_"):
            for entry, names in sorted(_once(sealed, prefix).items()):
                violations.append({
                    "assert": _ASSERT,
                    "artifact": code,
                    "violation": f"{entry!r} is classified more than once: {sorted(names)}",
                    "fix": "List each kind in exactly one group of each axis",
                })

    return {
        "assert_count": len(ontology),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
