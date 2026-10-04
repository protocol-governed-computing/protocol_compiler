"""
ASSERT_SUPERSEDED_NOT_REFERENCED_V0 Handler

Validates that:
1. Every artifact declaring `superseded_by` names at least one successor
2. Every named successor resolves to an artifact in the composition
3. No **live** artifact references a superseded one

Supersession is a declared relation between two exact identities, never a resolution rule. This
handler is what makes the declaration mean something: without it a superseded artifact stays
compiled, stays dispatchable, and everything that referenced it goes on reaching it — so a change
could stand a workflow down, report success, and leave the composition executing what it retired.

The closure binds live artifacts only. A retired artifact naming another retired one is coherent
history: an entry intent and the workflow it dispatched are stood down together, and each still says
what it said. Refusing that would oblige a change to rewrite the records it is retiring.

CONSTITUTIONAL: Pure rule checker — reads pre-computed structure from artifacts.
"""


def _identity(artifact: dict) -> tuple[str, str]:
    """An artifact's FQDN and its bare code, both of which a reference may legitimately use."""
    fqdn = str(artifact.get("fqdn_id") or "")
    return fqdn, fqdn.split("::")[-1] if fqdn else str(artifact.get("artifact_code") or "")


def _frontmatter(artifact: dict) -> dict:
    block = artifact.get("frontmatter")
    return block if isinstance(block, dict) else {}


# The supersession declaration is not a reference to what it replaces. Naming the artifact you stand
# in place of is the whole point of the relation; counting it as a reach would make every correct
# supersession its own violation.
DECLARATION_KEYS = {"supersedes", "superseded_by"}

def _successors(frontmatter: dict) -> list:
    """The successors an artifact names, however it names them.

    `superseded_by` is written as a list by construction and may be written as one identity by hand,
    and both are the same declaration. Iterating the scalar form yields its characters: one
    hand-authored supersession reported fifty-one violations, one per character of the successor's
    FQDN, each claiming a successor named `t`, `r`, `a`… and the whole of it read as fifty-one
    references to a retired artifact. Normalizing here is what makes the two spellings one fact.
    """
    value = frontmatter.get("superseded_by")
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)



def _references(value, found: set) -> set:
    """Every string an artifact carries, anywhere in its machine block.

    Walked whole rather than read at known keys. A reference is a reference wherever it sits, and a
    handler that looked only where references are *expected* would miss the one place a design put
    an identity nobody anticipated — which is exactly the reference that survives a retirement.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            if key in DECLARATION_KEYS:
                continue
            _references(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _references(item, found)
    elif isinstance(value, str):
        found.add(value)
    return found


def execute(artifacts: list[dict], compilation_context: dict) -> dict:
    violations = []

    superseded: dict[str, dict] = {}      # fqdn -> the artifact standing down
    by_identity: dict[str, str] = {}      # fqdn and bare code -> fqdn
    for artifact in artifacts:
        fqdn, bare = _identity(artifact)
        if not fqdn:
            continue
        by_identity[fqdn] = fqdn
        by_identity.setdefault(bare, fqdn)
        if _frontmatter(artifact).get("superseded_by"):
            superseded[fqdn] = artifact

    for fqdn, artifact in sorted(superseded.items()):
        successors = _successors(_frontmatter(artifact))
        if not successors:
            violations.append({
                "fqdn": fqdn,
                "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                "message": (f"{fqdn} declares superseded_by with no successor — 'superseded' with "
                            f"nothing standing in its place is a deletion wearing a softer word"),
                "fix": "Name the artifact that stands in its place, or delete it deliberately.",
            })
        for successor in successors:
            if str(successor) not in by_identity:
                violations.append({
                    "fqdn": fqdn,
                    "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                    "message": (f"{fqdn} is superseded by {successor}, which is not in this "
                                f"composition — the artifact standing in its place must exist"),
                    "fix": f"Author {successor}, or correct the successor named.",
                })

    if not superseded:
        return {"assert_count": len(artifacts), "violations": [], "status": "PASSED"}

    for artifact in artifacts:
        fqdn, _ = _identity(artifact)
        # A retired artifact may name another. The closure is about what the composition can still
        # reach, and nothing reaches either of these.
        if not fqdn or fqdn in superseded:
            continue
        for value in _references(_frontmatter(artifact), set()):
            target = by_identity.get(value)
            if target and target in superseded and target != fqdn:
                successors = ", ".join(_successors(_frontmatter(superseded[target])))
                violations.append({
                    "fqdn": fqdn,
                    "rule": "artifact::INVARIANT_SUPERSEDED_NOT_REFERENCED_V0",
                    "message": (f"{fqdn} references {target}, which is superseded by {successors}. "
                                f"A superseded artifact is unreachable — reaching it means the "
                                f"composition still runs what the design stood down"),
                    "fix": f"Re-point the reference at one of: {successors}",
                })

    return {
        "assert_count": len(artifacts),
        "violations": violations,
        "status": "FAILED" if violations else "PASSED",
    }
